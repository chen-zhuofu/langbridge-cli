"""Flat workflow entry: router → planner → todo loop → specialists."""
from langbridge_code.agents import control
from langbridge_code.agents.limits import now, over_time_budget
from langbridge_code.agents.roles import CHAT_SYSTEM_PROMPT
from langbridge_code.llm.client import create_model_response
from langbridge_code.llm.parse import extract_output_text, print_step_trace
from langbridge_code.persistence.context import recent_chat_turns
from langbridge_code.persistence.logging import write_finish_log, write_input_log
from langbridge_code.settings import MAX_WORKFLOW_SECONDS, WORKFLOW_OUTER_MULTIPLIER
from langbridge_code.tools.plan import read_todo_list
from langbridge_code.workflow import todo as todo_mod
from langbridge_code.workflow.coder_reviewer import run_coder_reviewer_loop
from langbridge_code.workflow.planner import initial_plan_prompt, refine_plan_prompt, run_planner
from langbridge_code.workflow.presenter import run_presenter_task
from langbridge_code.workflow.phases import emit_phase
from langbridge_code.workflow.router import route


def run_workflow(
    api_key,
    model,
    target,
    run_log_path,
    turn_id,
    trace_sink=None,
    print_reply=True,
    approval_callback=None,
    phase_sink=None,
    messages=None,
):
    """Run one user turn through the flat workflow (runs to todo completion)."""
    if messages is None:
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

    write_input_log(run_log_path, turn_id, messages + [{"role": "user", "content": target}])
    workflow_start = now()

    emit_phase(phase_sink, "routing")
    decision = route(
        api_key,
        model,
        target,
        messages=messages,
        trace_sink=trace_sink,
    )
    if decision["kind"] == "chat":
        emit_phase(phase_sink, "summarizing")
        reply = _chat_reply(api_key, model, messages, target, trace_sink=trace_sink)
        return _finish_turn(messages, target, reply, run_log_path, turn_id, print_reply)

    user_task = decision["task_summary"] or target
    task_type = decision["task_type"]
    has_open_todos = todo_mod.unfinished_count(todo_mod.load_tasks(run_log_path)) > 0
    if not has_open_todos:
        if decision["hard"]:
            emit_phase(phase_sink, "planning")
            run_planner(
                api_key,
                model,
                initial_plan_prompt(user_task, task_type=task_type),
                trace_sink=trace_sink,
                run_log_path=run_log_path,
                turn_id=turn_id,
            )
        else:
            tasks = todo_mod.single_task(user_task)
            todo_mod.save_tasks(tasks, run_log_path)

    context = _build_workflow_context(messages, target, decision)
    outer_limit = max(1, todo_mod.unfinished_count(todo_mod.load_tasks(run_log_path)) * WORKFLOW_OUTER_MULTIPLIER)
    outer_round = 0
    completed: list[str] = []

    while outer_round < outer_limit:
        control.checkpoint()
        if over_time_budget(workflow_start, MAX_WORKFLOW_SECONDS):
            break

        tasks = todo_mod.load_tasks(run_log_path)
        remaining = todo_mod.unfinished_count(tasks)
        if remaining == 0:
            break
        outer_limit = max(outer_limit, remaining * WORKFLOW_OUTER_MULTIPLIER)

        task = todo_mod.first_unfinished(tasks)
        if task is None:
            break

        outer_round += 1
        passed = False
        detail = ""

        if task_type == "coding":
            emit_phase(phase_sink, "coding")
            passed, detail = run_coder_reviewer_loop(
                api_key,
                model,
                task.description,
                context,
                trace_sink=trace_sink,
                phase_sink=phase_sink,
                run_log_path=run_log_path,
                turn_id=turn_id,
                approval_callback=approval_callback,
            )
        elif task_type == "presentation":
            emit_phase(phase_sink, "presenting")
            passed, detail = run_presenter_task(
                api_key,
                model,
                task.description,
                context,
                trace_sink=trace_sink,
                approval_callback=approval_callback,
                run_log_path=run_log_path,
                turn_id=turn_id,
            )

        if passed:
            todo_mod.mark_done(tasks, task)
            todo_mod.save_tasks(tasks, run_log_path)
            completed.append(task.description)
            continue

        emit_phase(phase_sink, "refining")
        run_planner(
            api_key,
            model,
            refine_plan_prompt(
                task.description,
                detail,
                read_todo_list(run_log_path),
                task_type=task_type,
            ),
            trace_sink=trace_sink,
            run_log_path=run_log_path,
            turn_id=turn_id,
        )

    emit_phase(phase_sink, "summarizing")
    tasks = todo_mod.load_tasks(run_log_path)
    if todo_mod.unfinished_count(tasks) == 0 and completed:
        reply = "Workflow complete.\n\nFinished:\n" + "\n".join(f"- {item}" for item in completed)
    elif completed:
        pending = [t for t in tasks if t.unfinished]
        reply = (
            "Workflow stopped before all tasks finished.\n\n"
            "Completed:\n"
            + "\n".join(f"- {item}" for item in completed)
            + "\n\nStill open:\n"
            + "\n".join(f"- {t.description}" for t in pending)
        )
    else:
        reply = "Workflow could not complete the todo list. Check logs and todo_list."

    return _finish_turn(messages, target, reply, run_log_path, turn_id, print_reply)


def _chat_reply(api_key, model, messages, user_message, *, trace_sink=None):
    chat_input = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    chat_input.extend(recent_chat_turns(messages))
    chat_input.append({"role": "user", "content": user_message})

    data = create_model_response(api_key, model, chat_input, label="Chat")
    output = data.get("output", [])
    if trace_sink is not None:
        print_step_trace(output, include_message=True, label="Chat", sink=trace_sink)
    text = extract_output_text(output).strip()
    return text or "Hello."


def _build_workflow_context(messages, target, decision):
    lines = []
    prior = recent_chat_turns(messages)
    if prior:
        transcript = "\n".join(
            f"{'User' if turn['role'] == 'user' else 'Assistant'}: {turn['content']}"
            for turn in prior[-8:]
        )
        lines.append(f"Conversation so far:\n{transcript}")
    lines.append(f"Latest user request:\n{target}")
    task_summary = (decision.get("task_summary") or "").strip()
    if task_summary and task_summary != target.strip():
        lines.append(f"Task focus:\n{task_summary}")
    return "\n\n".join(lines)


def _finish_turn(messages, target, reply, run_log_path, turn_id, print_reply):
    messages.append({"role": "user", "content": target})
    messages.append({"role": "assistant", "content": reply})
    write_finish_log(run_log_path, turn_id, reply)
    if print_reply:
        print(f"\n{reply}\n")
    return reply

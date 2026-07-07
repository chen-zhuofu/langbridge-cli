"""Agent entry points for the coder/reviewer workflow."""
from langbridge_code.workflow.coder_reviewer import run_coder_reviewer_loop


def run_coder_component(api_key, model, arguments, trace_sink=None, run_log_path=None, turn_id=None, approval_callback=None):
    task = arguments.get("task", "")
    context = arguments.get("context", "")
    passed, detail = run_coder_reviewer_loop(
        api_key,
        model,
        task,
        context,
        trace_sink=trace_sink,
        run_log_path=run_log_path,
        turn_id=turn_id,
        approval_callback=approval_callback,
    )
    status = "OK" if passed else "NEEDS_WORK"
    return f"{detail}\n\nWORKFLOW_REVIEW_STATUS: {status}"


def run_tool_call(*args, **kwargs):
    raise NotImplementedError("Use run_workflow for the full workflow.")

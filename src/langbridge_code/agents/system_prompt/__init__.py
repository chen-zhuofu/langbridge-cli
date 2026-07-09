from langbridge_code.agents.system_prompt.explorer import EXPLORER_PROMPT, explorer_system_prompt
from langbridge_code.agents.system_prompt.langbridge import LANGBRIDGE_PROMPT, langbridge_system_prompt
from langbridge_code.agents.system_prompt.planner import PLANNER_PROMPT, planner_system_prompt
from langbridge_code.agents.system_prompt.reviewer import REVIEWER_ENGINEER_PROMPT, reviewer_system_prompt
from langbridge_code.agents.system_prompt.worker import WORKER_ENGINEER_PROMPT, worker_system_prompt

# Back-compat aliases
CODER_ENGINEER_PROMPT = WORKER_ENGINEER_PROMPT
coder_system_prompt = worker_system_prompt

__all__ = [
    "CODER_ENGINEER_PROMPT",
    "EXPLORER_PROMPT",
    "LANGBRIDGE_PROMPT",
    "PLANNER_PROMPT",
    "REVIEWER_ENGINEER_PROMPT",
    "WORKER_ENGINEER_PROMPT",
    "coder_system_prompt",
    "explorer_system_prompt",
    "langbridge_system_prompt",
    "planner_system_prompt",
    "reviewer_system_prompt",
    "worker_system_prompt",
]

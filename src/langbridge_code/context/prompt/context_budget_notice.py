CONTEXT_BUDGET_MARKER = "\n\n---\nContext status (updated each step):"

CONTEXT_BUDGET_BODY = (
    "That threshold is a hard stop for this agent loop, like the time limit and "
    "max-step cap. It is not a per-turn ceiling — you may keep calling tools within "
    "a turn even as usage grows. "
    "When you are nearing the threshold, wrap up cleanly: finish the current work, "
    "run verification, and leave a coherent result instead of starting broad new "
    "exploration. Older tool output may be compacted automatically along the way."
)

CONTEXT_BUDGET_NEAR_LIMIT = (
    "You are close to the loop stop threshold — prioritize finishing and verifying now."
)

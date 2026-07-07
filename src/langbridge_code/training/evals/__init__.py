"""Eval runners for workflow roles.

Each runner is pure orchestration over an injected agent callable and an injected
grader, so the scoring logic is unit-testable with stubs (no LLM, no repo). The
real callables that drive the actual agents against a target repo live in
`agents_adapter.py`.
"""

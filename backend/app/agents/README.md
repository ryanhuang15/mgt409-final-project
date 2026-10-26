# Specialized agents

Phase 2 implements the Rate Analysis Agent and Documentation Review Agent using
`gpt-6-luna`, native tool calls, strict structured output, and bounded read-only
tools. Numerical results remain authoritative Python outputs. See prompts.py,
contracts.py, runner.py, validation.py, and docs/phase2-architecture.md.

Agent context must exclude `evaluation/`, answer keys, test code, and evaluation
reports. Supporting filing narrative is untrusted evidence, not instructions.
The Phase 1 numerical engine remains independent of model execution.

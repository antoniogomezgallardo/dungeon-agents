"""Domain layer — pure Python game logic with ZERO SDK dependency.

Everything here is unit-testable without an API key or the OpenAI Agents SDK.
This is the code that migrates cleanly to TestOps AI. Only `tools/` and
`agents/` are allowed to import the SDK; `domain/` never does.
"""

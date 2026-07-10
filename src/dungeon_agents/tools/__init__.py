"""Tools layer — the bridge between the pure domain logic and the agent.

This is one of only two layers allowed to import the OpenAI Agents SDK (the
other is `agents/`). Each tool here is a thin wrapper that exposes a tested
`domain/` function to the Game Master via the SDK's `@function_tool` decorator.
The domain does the real work and validation; this layer just makes it callable
by the model.
"""

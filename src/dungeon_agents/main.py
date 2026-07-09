"""Console entry point for Dungeon Agents (Milestone 1).

Runs an interactive loop: the player types an action, the Game Master responds
with a short scene and 2-3 choices. Type `exit` (or `quit`) to leave.

Design notes:
- All I/O lives here; the agent itself lives in `agents/game_master.py`. That
  separation keeps the agent testable without a running console.
- We keep the running conversation so the Game Master has context across turns.
  The SDK's `Runner.run_sync(...).to_input_list()` gives us the accumulated
  history to feed back into the next turn.
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from dungeon_agents.agents.game_master import build_game_master
from dungeon_agents.config import load_settings

EXIT_WORDS = {"exit", "quit"}
OPENING_PROMPT = "Begin the adventure. Set an opening scene and offer me my first choices."

console = Console()


def _print_scene(text: str) -> None:
    """Render a Game Master reply as Markdown inside a titled panel."""
    console.print(Panel(Markdown(text), title="Game Master", border_style="magenta"))


def run() -> None:
    """Run the interactive game loop until the player exits."""
    settings = load_settings()

    if not settings.has_api_key:
        console.print(
            f"[bold red]No {settings.api_key_env_name} found.[/bold red] "
            f"(provider: [cyan]{settings.provider}[/cyan]) "
            "Copy [cyan].env.example[/cyan] to [cyan].env[/cyan] and add your key, "
            "then run again."
        )
        return

    # Imported lazily so the "no key" message above never trips over a missing SDK.
    from agents import Runner

    game_master = build_game_master(settings)

    console.print(
        Panel(
            "[bold]Dungeon Agents[/bold] — type an action, or [cyan]exit[/cyan] to quit.\n"
            f"[dim]{settings.provider} · {settings.model}[/dim]",
            border_style="green",
        )
    )

    # The conversation history fed into each turn. Starts with the opening prompt.
    conversation: list = [{"role": "user", "content": OPENING_PROMPT}]

    while True:
        result = Runner.run_sync(game_master, conversation)
        _print_scene(result.final_output)
        # Carry the full history forward so the next turn keeps context.
        conversation = result.to_input_list()

        try:
            player_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Farewell, adventurer.[/dim]")
            return

        if player_input.lower() in EXIT_WORDS:
            console.print("[dim]Farewell, adventurer.[/dim]")
            return
        if not player_input:
            continue

        conversation.append({"role": "user", "content": player_input})


def main() -> None:
    """Console-script entry point (see pyproject `[project.scripts]`)."""
    run()


if __name__ == "__main__":
    main()

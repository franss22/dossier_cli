"""Console message helpers for Dossier."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def info(message: str) -> None:
    """Print an informational message to the console."""
    console.print(f"[cyan]→[/cyan] {message}")


def success(message: str) -> None:
    """Print a success message to the console."""
    console.print(f"[green]✓[/green] {message}")


def error(message: str) -> None:
    """Print an error message to the console."""
    console.print(f"[red]✗[/red] {message}")


def print_run_header(
    title: str,
    **categories: dict[str, str],
) -> None:
    """Print a formatted run header with categorized information."""
    lines: list[Text] = []

    for name, values in categories.items():
        name = name.replace("_", " ").title()
        lines.append(Text(name, style="bold"))

        for key, value in values.items():
            lines.append(
                Text.assemble(
                    ("  " + key.ljust(12), "cyan"),
                    value,
                )
            )

        lines.append(Text(""))

    console.print(
        Panel(
            Text("\n").join(lines).rstrip() or Text(""),
            title=title,
            expand=False,
        )
    )

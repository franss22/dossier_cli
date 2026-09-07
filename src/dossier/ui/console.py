"""Console message helpers for Dossier."""

from pathlib import Path

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


def path_success(label: str, path: Path) -> None:
    """Print a success message with a clickable path label."""
    console.print(_path_message("[green]✓[/green]", label, path))


def path_info(label: str, path: Path) -> None:
    """Print an informational message with a clickable path label."""
    console.print(_path_message("[cyan]→[/cyan]", label, path))


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


def _path_message(prefix: str, label: str, path: Path) -> Text:
    """Format a short clickable path with a repo-relative fallback display."""
    resolved_path = path.resolve()
    display_name = resolved_path.name

    try:
        compact_path = resolved_path.relative_to(Path.cwd())
    except ValueError:
        compact_path = resolved_path

    message = Text.from_markup(f"{prefix} {label}: ")
    filename = Text(display_name, style=f"link {resolved_path.as_uri()} underline")
    location = Text(f" ({compact_path.as_posix()})", style="dim")
    message.append_text(filename)
    message.append_text(location)
    return message

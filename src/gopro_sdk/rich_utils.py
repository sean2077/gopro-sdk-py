"""Rich utilities for formatting and display."""

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

# Global console instance
console = Console()


def create_progress() -> Progress:
    """
    Create a progress bar with standard columns.

    Returns:
        Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def create_table(title: str, *columns: str, **kwargs) -> Table:
    """
    Create a table with standard styling.

    Args:
        title: Table title
        *columns: Column names
        **kwargs: Additional Table arguments

    Returns:
        Table instance
    """
    table = Table(title=title, **kwargs)
    for col in columns:
        table.add_column(col)
    return table


__all__ = [
    "console",
    "Console",
    "Progress",
    "Table",
    "create_progress",
    "create_table",
]

# ai_cdss_api/cli.py
import logging

import typer
import uvicorn

logger = logging.getLogger(__name__)

cli = typer.Typer(help="CLI for the AI-CDSS FastAPI server.")


@cli.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    reload: bool = typer.Option(True, help="Enable auto-reload."),
    reload_dirs: list[str] = typer.Option(
        None,  # Default to None, so typer knows it can collect multiple values
        "--reload-dir",
        "-rd",
        help="Additional directories to watch for reload. Can be specified multiple times.",
        rich_help_panel="Reload Options",
    ),
):
    """Start the FastAPI server."""
    uvicorn.run(
        "ai_cdss_api.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=reload_dirs if reload_dirs else None,
    )

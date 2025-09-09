# ai_cdss_api/cli.py
import logging
from pathlib import Path

import typer
import uvicorn
from dotenv import load_dotenv

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
    env_file: Path | None = typer.Option(
        None, "--env-file", "-e", help="Path to a .env file (optional)"
    ),
):
    """Start the FastAPI server."""

    # Load .env into process env so Pydantic can read it
    if env_file and env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        # Optional: try a local .env if present
        load_dotenv(".env", override=False)

    uvicorn.run(
        "ai_cdss_api.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=reload_dirs if reload_dirs else None,
    )

# ai_cdss_api/cli.py
import typer
import uvicorn
import logging

logging.basicConfig(
    level=logging.DEBUG, # Default to INFO if not specified via CLI
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

cli = typer.Typer(
    help="CLI for the AI-CDSS FastAPI server."
)

@cli.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    reload: bool = typer.Option(True, help="Enable auto-reload."),
    reload_dirs: list[str] = typer.Option(
        None, # Default to None, so typer knows it can collect multiple values
        "--reload-dir",
        "-rd",
        help="Additional directories to watch for reload. Can be specified multiple times.",
        rich_help_panel="Reload Options"
    ),
    log_level: str = typer.Option(
        "info",
        "--log-level",
        "-l",
        help="Set the logging level (debug, info, warning, error, critical).",
        rich_help_panel="Logging Options"
    )
):
    """Start the FastAPI server."""
    # Convert string level (e.g., "debug") to Python's numeric logging level (e.g., logging.DEBUG)
    # numeric_level = getattr(logging, log_level.upper(), None)

    # # Validate if the provided log level string is valid
    # if not isinstance(numeric_level, int):
    #     logger.error(f"Invalid log level specified: '{log_level}'. Defaulting to INFO.")
    #     numeric_level = logging.INFO

    # # Set the level for the root logger. This affects all loggers throughout your application.
    # logging.getLogger().setLevel(numeric_level)
    # logger.info(f"Application logging level set to: {logging.getLevelName(numeric_level)}")

    uvicorn.run("ai_cdss_api.main:app", host=host, port=port, reload=reload, reload_dirs=reload_dirs if reload_dirs else None)


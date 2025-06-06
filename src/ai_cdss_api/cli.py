# ai_cdss_api/cli.py
import typer
import uvicorn

cli = typer.Typer()

@cli.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    reload: bool = typer.Option(True, help="Enable auto-reload.")
):
    """Start the FastAPI server."""
    uvicorn.run("ai_cdss_api.main:app", host=host, port=port, reload=reload)


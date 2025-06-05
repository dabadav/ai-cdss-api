# ai_cdss_api/cli.py
import typer
import uvicorn

cli = typer.Typer()

@cli.command()
def run(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True
):
    """Start the FastAPI server."""
    uvicorn.run("ai_cdss_api.main:app", host=host, port=port, reload=reload)


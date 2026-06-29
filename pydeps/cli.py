import typer
from pydeps.watcher import start_watching
app = typer.Typer()

@app.command()
def watch(path: str = "."):
    """Watch project and auto-update requirements.txt"""
    print(f"[pydeps] Watching {path} ...")
    start_watching(path)

def main():
    app()
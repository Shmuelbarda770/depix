import typer
from depix.watcher import start_watching
app = typer.Typer()

@app.command()
def watch(path: str = "."):
    """Watch project and auto-update requirements.txt"""
    print(f"[depix] Watching {path} ...")
    start_watching(path)

def main():
    app()
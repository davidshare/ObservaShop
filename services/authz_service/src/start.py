import subprocess
import uvicorn
from main import app


def run_migrations():
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    run_migrations()
    uvicorn.run(app, host="0.0.0.0", port=8000)

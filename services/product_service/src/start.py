import subprocess
import uvicorn
from main import app
from src.config.logger_config import log


def run_migrations():
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    APP_HOST = "0.0.0.0"
    APP_PORT = 8012
    run_migrations()
    log.info("Starting product-service on {}:{}", APP_HOST, APP_PORT)
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)

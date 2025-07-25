import subprocess
import uvicorn
from loguru import logger
from main import app


def run_migrations():
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    APP_HOST = "0.0.0.0"
    APP_PORT = 8000
    run_migrations()
    logger.info("Starting auth-service on {}:{}", APP_HOST, APP_PORT)
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)

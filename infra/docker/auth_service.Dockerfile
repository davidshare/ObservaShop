FROM python:3.10-slim

WORKDIR /app

RUN pip install uv

COPY shared /app/shared
COPY services/auth_service /app

ENV PYTHONPATH=/app

RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "python", "src/start.py"]
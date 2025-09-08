FROM python:3.10-slim

WORKDIR /app/service

COPY uv.lock /app/service/uv.lock

RUN pip install uv

COPY shared /app/shared
COPY services/product_service /app/service

ENV PYTHONPATH="/app:/app/service"

RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "python", "/app/service/src/start.py"]
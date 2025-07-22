FROM python:3.10-slim

WORKDIR /app

RUN pip install uv

COPY shared /app/shared
COPY services/payment_service /app

RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "python", "src/start.py"]
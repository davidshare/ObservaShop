FROM python:3.10-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy shared and service code
COPY shared /app/shared
COPY services/payment_service /app

# Install dependencies with uv
RUN uv sync

# Expose port
EXPOSE 8000

# Run FastAPI app
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.11-slim

WORKDIR /app

# Stop Python from buffering outputs
ENV PYTHONUNBUFFERED=1

# Copy dependency definition
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code into container
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Start server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Use an official Python imageAdd commentMore actions
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose the FastAPI port
EXPOSE 9765

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9765"]

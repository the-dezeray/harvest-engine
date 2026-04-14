# Start from Python 3.11
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy and install dependencies first
# Docker caches this layer — so if requirements don't change, it skips reinstalling
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# This container listens on port 8000
EXPOSE 8000

# Command that runs when the container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
# Use the official Python 3.12 image (slim variant is smaller)
FROM python:3.12-slim

# Create app directory
WORKDIR /app

# Install system dependencies if needed (uncomment or add as needed)
# RUN apt-get update && apt-get install -y <PACKAGES> && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the codebase
COPY . /app/

# Expose any port if needed (Telegram Bot via polling doesn’t need an external port)
# EXPOSE 8000

# Define default command
CMD ["python", "main.py"]

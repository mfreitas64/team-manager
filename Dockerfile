# Dockerfile
FROM python:3.11-slim

# Install WeasyPrint dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Expose the Flask port
EXPOSE 10000

# Command to run the app
CMD ["flask", "run", "--host=0.0.0.0", "--port=10000"]
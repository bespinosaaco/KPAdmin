FROM python:3.13.2-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create non-root user and set permissions
RUN useradd -u 1005 -M -s /bin/bash KPAdmin && \
    chown -R KPAdmin:KPAdmin /app

# Switch to non-root user
USER KPAdmin

EXPOSE 8080

# Healthcheck for Streamlit
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health || exit 1

# Run Streamlit
ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8080", "--server.address=0.0.0.0"]
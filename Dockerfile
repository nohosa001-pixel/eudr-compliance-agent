FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for geospatial libraries (GEOS, GDAL, PROJ) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first for Docker layer caching
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy full application code
COPY . .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Intelligent Dual-Mode Entrypoint:
# - Runs uvicorn on Google Cloud Run (when $PORT is defined)
# - Runs mcp_server_stdio.py on Glama / Smithery / Docker stdio inspectors (when $PORT is empty)
ENTRYPOINT ["/app/entrypoint.sh"]

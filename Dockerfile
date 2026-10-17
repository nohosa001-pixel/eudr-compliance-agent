# ==========================================
# Stage 1: Build & Wheels compilation stage
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --user -r requirements.txt

# ==========================================
# Stage 2: Minimal Runtime stage
# ==========================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Only install runtime shared libraries (no build-essential, no dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgeos-c1v5 \
    libproj25 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application source code
COPY . .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Intelligent Dual-Mode Entrypoint:
# - Runs uvicorn on Google Cloud Run (when $PORT is defined)
# - Runs mcp_server_stdio.py on Glama / Smithery / Docker stdio inspectors (when $PORT is empty)
ENTRYPOINT ["/app/entrypoint.sh"]


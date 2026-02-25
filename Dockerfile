FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml ./
COPY src/ ./src/

# Install portal
RUN pip install --no-cache-dir -e ".[all]" || pip install --no-cache-dir -e "."

EXPOSE 8081

CMD ["uvicorn", "portal.interfaces.web.server:WebInterface", "--host", "0.0.0.0", "--port", "8081", "--app-dir", "src"]

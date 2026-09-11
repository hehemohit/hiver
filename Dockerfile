# Build upon official lightweight Python 3.11 image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src:/app"

WORKDIR /app

# Install build tools if required by any compiled dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies first for optimal layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source, data, evaluations, and tests
COPY src/ ./src/
COPY evaluation/ ./evaluation/
COPY data/processed/ ./data/processed/
COPY data/chroma_db/ ./data/chroma_db/
COPY data/golden_set.jsonl ./data/golden_set.jsonl
COPY data/GOLDEN_SET_METHODOLOGY.md ./data/GOLDEN_SET_METHODOLOGY.md
COPY tests/ ./tests/
COPY reports/ ./reports/
COPY demo.py .
COPY diagnose.py .
COPY edgecases.md .
COPY QNA.md .
COPY README.md .
COPY .env.example .

# Default command: Runs the preset support scenarios demonstration
CMD ["python", "demo.py", "--preset"]

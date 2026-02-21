# AutoCodeRover Production Dockerfile
# Optimized with permanent dependencies

FROM continuumio/miniconda3:24.1.2-0

LABEL maintainer="RepoWise Team"
LABEL description="AutoCodeRover - Automated Code Fixing with LLMs"
LABEL version="1.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    git \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/auto-code-rover

# Copy AutoCodeRover source code
COPY auto-code-rover/ .

# Copy wrapper API
COPY wrapper_api.py .

# Create conda environment from environment.yml
RUN conda env create -f environment.yml && \
    conda clean -afy

# Activate environment and install missing dependencies
# These packages are not in environment.yml but required by AutoCodeRover
# List verified by actual runtime testing
RUN /opt/conda/envs/auto-code-rover/bin/pip install --no-cache-dir \
    loguru \
    natsort \
    tenacity \
    pylint \
    timeout_decorator \
    ollama \
    unidiff \
    coverage \
    emojis

# Install wrapper API dependencies
RUN /opt/conda/envs/auto-code-rover/bin/pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.6.0

# Set environment variables
ENV PATH=/opt/conda/envs/auto-code-rover/bin:$PATH \
    CONDA_DEFAULT_ENV=auto-code-rover \
    CONDA_PREFIX=/opt/conda/envs/auto-code-rover \
    PYTHONPATH=/opt/auto-code-rover \
    PYTHONUNBUFFERED=1

# Create directories for volumes
RUN mkdir -p /repos /outputs /tmp/workdir

# Expose API port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default command
CMD ["python", "wrapper_api.py"]

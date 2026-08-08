# Stage 1 - Build using Debian Slim
FROM python:3.11-slim AS builder

WORKDIR /app

# Create a virtual environment to bundle all Python dependencies smoothly
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip to ensure clean wheel evaluations
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

# Install dependencies cleanly into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2 - Runner using Debian Slim
FROM python:3.11-slim AS runner

# Create a non-root user and group with fixed ID
RUN groupadd -g 1234 appgroup && \
    useradd -u 1234 -g appgroup -s /usr/sbin/nologin -d /app appuser

WORKDIR /app

# Copy the built virtual environment from the builder stage
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application source code
COPY . .

# Switch to non-root user
USER appuser

EXPOSE 5000

# Exec form allows application to catch OS signals gracefully
CMD ["python", "main.py"]

# ------------------------------ Builder Stage ------------------------------ #
FROM python:3.12-bullseye AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies and build TA-Lib (ARM64 safe)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        wget \
        dpkg-dev \
        ca-certificates \
    && \
    # Download TA-Lib source
    wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    \
    # ---- FIX: update autotools for aarch64 / arm64 ----
    wget -O config.guess https://git.savannah.gnu.org/cgit/config.git/plain/config.guess && \
    wget -O config.sub https://git.savannah.gnu.org/cgit/config.git/plain/config.sub && \
    chmod +x config.guess config.sub && \
    \
    # Configure, build and install
    ./configure \
        --prefix=/usr \
        --build="$(dpkg-architecture -q DEB_BUILD_GNU_TYPE)" && \
    make -j"$(nproc)" && \
    make install && \
    \
    # Cleanup build artifacts
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz && \
    ldconfig && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency descriptors
COPY pyproject.toml .
COPY requirements.txt .

# Create virtual environment using uv and install Python deps
RUN pip install --no-cache-dir uv && \
    uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install --upgrade pip && \
    uv pip install -r requirements.txt && \
    uv pip install gunicorn && \
    rm -rf /root/.cache

# --------------------------------------------------------------------------- #
# ------------------------------ Production Stage --------------------------- #
FROM python:3.12-slim-bullseye AS production

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata \
        curl \
        ca-certificates \
    && \
    # Set timezone to Asia/Kolkata
    ln -fs /usr/share/zoneinfo/Asia/Kolkata /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy TA-Lib runtime libraries and headers
COPY --from=builder /usr/lib/libta_lib* /usr/lib/
COPY --from=builder /usr/include/ta-lib /usr/include/ta-lib
RUN ldconfig

# Create non-root user
RUN useradd --create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application source
COPY --chown=appuser:appuser . .

# Create required directories and set permissions
RUN mkdir -p \
        /app/logs \
        /app/instance \
        /app/flask_session \
        /app/migrations \
    && \
    chown -R appuser:appuser \
        /app/logs \
        /app/instance \
        /app/flask_session \
        /app/migrations \
    && \
    chmod -R 755 \
        /app/logs \
        /app/instance \
        /app/flask_session \
    && \
    touch /app/.env && \
    chown appuser:appuser /app/.env && \
    chmod 666 /app/.env

# Entrypoint script
COPY --chown=appuser:appuser start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# Runtime environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Kolkata \
    FLASK_APP=app:create_app \
    FLASK_ENV=production

USER appuser

EXPOSE 8000

CMD ["/app/start.sh"]

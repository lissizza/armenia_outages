# Stage 1: Install Python dependencies
FROM python:3.12-slim as builder

WORKDIR /app

COPY requirements.txt .

# Install the dependencies and postgresql-client
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client \
    git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Use a base image with Chrome and Selenium pre-installed
FROM selenium/standalone-chrome:latest

# No USER root command since the default user is non-root in selenium/standalone-chrome

WORKDIR /app

# Copy Python installation from builder
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include /usr/local/include
COPY --from=builder /usr/local/share /usr/local/share

# Copy postgresql-client from builder
COPY --from=builder /usr/bin/psql /usr/bin/psql
COPY --from=builder /usr/share/postgresql /usr/share/postgresql
COPY --from=builder /usr/lib/postgresql /usr/lib/postgresql

# Copy the application code
COPY . /app

# Set environment variables for Python to ensure output is not buffered
ENV PYTHONUNBUFFERED=1


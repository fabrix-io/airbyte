FROM python:3.10-slim as base

# Install 1Password CLI
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && curl -sSfLo op.zip https://cache.agilebits.com/dist/1P/op2/pkg/v2.24.0/op_linux_amd64_v2.24.0.zip \
    && unzip -od /usr/local/bin/ op.zip \
    && rm op.zip \
    && chmod +x /usr/local/bin/op \
    && apt-get remove -y curl unzip \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
FROM base as builder
WORKDIR /airbyte/integration_code

# Install poetry
RUN pip install --upgrade pip
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only main

# Copy source code
COPY . .

# Install the connector
RUN poetry install

# Runtime
FROM base as runtime
WORKDIR /airbyte/integration_code

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /airbyte/integration_code /airbyte/integration_code

ENV PYTHONPATH=/airbyte/integration_code

# Run the connector
ENTRYPOINT ["python", "/airbyte/integration_code/main.py"]

LABEL io.airbyte.version=0.1.0
LABEL io.airbyte.name=airbyte/source-onepassword
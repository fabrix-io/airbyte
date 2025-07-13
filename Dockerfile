FROM python:3.9-slim

# Install any system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /airbyte/integration_code

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY . .

ENV PYTHONPATH=/airbyte/integration_code
ENV AIRBYTE_ENTRYPOINT="python /airbyte/integration_code/main.py"

ENTRYPOINT ["python", "/airbyte/integration_code/main.py"]

LABEL io.airbyte.version=0.1.0
LABEL io.airbyte.name=airbyte/source-hashicorp-vault
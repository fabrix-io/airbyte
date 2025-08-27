FROM airbyte/python-connector-base:2.0.0

# Install ODBC driver and dependencies for SQL Server
USER root
RUN apt-get update && \
    apt-get install -y \
    curl \
    apt-transport-https \
    gnupg \
    lsb-release \
    unixodbc \
    unixodbc-dev \
    krb5-user \
    libkrb5-dev && \
    # Add Microsoft repository with proper key handling
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    # Install Microsoft ODBC drivers (latest version)
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    # Try to install older Microsoft drivers if available for the architecture
    (ACCEPT_EULA=Y apt-get install -y msodbcsql17 || true) && \
    (ACCEPT_EULA=Y apt-get install -y msodbcsql13 || true) && \
    # Install FreeTDS as a fallback driver (provides generic "SQL Server" driver)
    apt-get install -y freetds-dev tdsodbc && \
    # Install PostgreSQL ODBC driver
    apt-get install -y odbc-postgresql && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    # Verify driver installation
    echo "Installed ODBC drivers:" && odbcinst -q -d

# Copy code and install dependencies
COPY . /airbyte/integration_code
WORKDIR /airbyte/integration_code

# Install poetry and dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main

ENV AIRBYTE_ENTRYPOINT="python /airbyte/integration_code/main.py"
ENTRYPOINT ["python", "/airbyte/integration_code/main.py"]

LABEL io.airbyte.version=0.1.0
LABEL io.airbyte.name=airbyte/source-odbc

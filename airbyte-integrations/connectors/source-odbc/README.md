# ODBC Source

This is the repository for the ODBC source connector, which connects to ODBC-compatible databases using Active Directory authentication.

## Features

- Connects to ODBC-compatible databases
- Supports Active Directory authentication including Kerberos
- Support for various authentication methods:
  - ActiveDirectoryPassword
  - ActiveDirectoryIntegrated
  - ActiveDirectoryKerberos (using pure Python Kerberos implementation)
  - SqlServerAuthentication
- SSL/TLS encryption support
- Configurable connection timeouts

## Configuration

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `dsn` | string | Yes | Data Source Name or connection string | `"DRIVER={ODBC Driver 18 for SQL Server};SERVER=myserver;DATABASE=mydatabase;"` |
| `server` | string | Yes | Server hostname or IP address | `"sqlserver.domain.com"` |
| `database` | string | Yes | Database name | `"MyDatabase"` |
| `username` | string | Yes | Username for authentication | `"domain\\user"` or `"user@domain.com"` |
| `password` | string | Yes | Password for authentication | `"password123"` |
| `port` | integer | No | Port number (default: 1433) | `1433` |
| `driver` | string | No | ODBC driver name | `"ODBC Driver 18 for SQL Server"` |
| `authentication_type` | string | No | Authentication method | `"ActiveDirectoryKerberos"` |
| `realm` | string | No* | Kerberos realm (required for Kerberos auth) | `"DOMAIN.COM"` |
| `kdc_host` | string | No* | Key Distribution Center host (required for Kerberos auth) | `"dc01.domain.com"` |
| `encrypt` | boolean | No | Use encrypted connection | `true` |
| `trust_server_certificate` | boolean | No | Trust server certificate | `false` |
| `connection_timeout` | integer | No | Connection timeout in seconds | `30` |

*Required only when `authentication_type` is `"ActiveDirectoryKerberos"`

## Supported Authentication Types

- **ActiveDirectory**: Uses Active Directory password authentication
- **ActiveDirectoryIntegrated**: Uses integrated Windows authentication
- **ActiveDirectoryPassword**: Explicit Active Directory password authentication
- **ActiveDirectoryKerberos**: Pure Python Kerberos authentication using impacket library
- **SqlServerAuthentication**: Standard SQL Server authentication

## Kerberos Authentication

The connector supports pure Python Kerberos authentication using the impacket library. This method:

- Does not require system Kerberos libraries to be installed
- Automatically configures Kerberos settings
- Creates temporary credential cache files
- Automatically cleans up temporary files after connection

When using `ActiveDirectoryKerberos`:
1. Provide the `realm` (Kerberos domain in uppercase)
2. Provide the `kdc_host` (domain controller hostname or IP)
3. The connector will authenticate and create a Kerberos ticket
4. The ODBC connection uses `Trusted_Connection=Yes` with the generated ticket

## Local Development

### Prerequisites

- Python 3.10+
- Poetry
- ODBC drivers installed on your system

### Install Dependencies

```bash
poetry install
```

### Run Tests

```bash
poetry run pytest
```

### Build Docker Image

```bash
docker build -t airbyte/source-odbc:dev .
```

## Changelog

### 0.1.1
- Added ActiveDirectoryKerberos authentication support
- Integrated pure Python Kerberos authentication using impacket
- Added automatic cleanup of temporary Kerberos files
- Updated configuration schema with realm and kdc_host parameters

### 0.1.0
- Initial release with Active Directory authentication support
- Basic ODBC connectivity

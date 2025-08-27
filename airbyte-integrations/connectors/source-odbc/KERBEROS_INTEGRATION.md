# ODBC Source with Kerberos Authentication Integration

This document describes the integration of Active Directory Kerberos authentication into the ODBC source connector.

## What was integrated

The working Kerberos authentication code has been successfully integrated into the ODBC source connector with the following key components:

### 1. Dependencies Added
- `impacket = "^0.12.0"` - Pure Python Kerberos implementation

### 2. New Configuration Parameters
- `authentication_type: "ActiveDirectoryKerberos"` - New auth type for Kerberos
- `realm: string` - Kerberos realm (e.g., "FABRIX.LOCAL")
- `kdc_host: string` - Domain controller hostname/IP

### 3. Core Integration Features
- **Pure Python Kerberos**: Uses impacket library (no system Kerberos dependencies)
- **Automatic Configuration**: Generates Kerberos config files dynamically
- **Secure Credential Cache**: Creates temporary credential cache files with proper permissions
- **Automatic Cleanup**: Cleans up temporary files after connection attempts
- **Error Handling**: Proper validation and error messages

### 4. Key Methods Added
- `_setup_kerberos_config()`: Creates Kerberos configuration
- `_authenticate_with_kerberos()`: Performs Kerberos authentication

## Example Configuration

Based on your working code sample, here's the equivalent configuration for the ODBC connector:

```json
{
  "server": "ec2-3-88-19-18.compute-1.amazonaws.com",
  "database": "FabrixHR", 
  "username": "FABRIXSCANNER",
  "password": "Password1!",
  "port": 1433,
  "authentication_type": "ActiveDirectoryKerberos",
  "realm": "FABRIX.LOCAL",
  "kdc_host": "ec2-3-88-19-18.compute-1.amazonaws.com",
  "encrypt": true,
  "trust_server_certificate": true,
  "connection_timeout": 30
}
```

## How It Works

1. **Configuration Validation**: Checks that `realm` and `kdc_host` are provided for Kerberos auth
2. **Kerberos Setup**: Creates temporary krb5.conf with your domain settings
3. **Authentication**: Uses impacket to get TGT from domain controller
4. **Credential Cache**: Saves Kerberos ticket to temporary file
5. **ODBC Connection**: Uses `Trusted_Connection=Yes` which leverages the Kerberos ticket
6. **Cleanup**: Automatically removes temporary files

## Environment Variables Support

The connector can also use environment variables (like your original code):
- If not specified in config, it will look for standard environment variables
- This maintains compatibility with your existing setup

## Benefits of This Integration

1. **No External Dependencies**: Pure Python implementation
2. **Airbyte Integration**: Follows Airbyte connector patterns
3. **Secure**: Proper file permissions and cleanup
4. **Configurable**: All parameters configurable through Airbyte UI
5. **Robust Error Handling**: Clear error messages for troubleshooting

The integration maintains the core functionality of your working code while adapting it to the Airbyte connector framework.

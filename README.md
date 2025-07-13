# HashiCorp Vault Scanner

A Python-based scanner for HashiCorp Vault that uses AppRole authentication to collect configuration and metadata information across multiple data streams.

## Features

The scanner collects information from the following streams:

1. **Vault Info** - General information about the Vault instance (version, HA status, replication, etc.)
2. **Users** - User accounts (currently supports userpass auth method)
3. **Roles** - AppRole configurations
4. **Policies** - ACL policies and their rules
5. **Groups** - Identity groups and their members
6. **Namespaces** - Namespace hierarchy (scanned recursively)
7. **Secrets** - Secret metadata without values (scanned recursively)
8. **Permissions** - User and group policy assignments

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python vault_scanner.py \
    --vault-url https://vault.example.com:8200 \
    --role-id your-role-id \
    --secret-id your-secret-id
```

### Full Options

```bash
python vault_scanner.py \
    --vault-url https://vault.example.com:8200 \
    --role-id your-role-id \
    --secret-id your-secret-id \
    --namespace admin \
    --output results.json \
    --format json \
    --timeout 30 \
    --no-verify-ssl
```

### Parameters

- `--vault-url` (required): The URL of your Vault server
- `--role-id` (required): AppRole role ID for authentication
- `--secret-id` (required): AppRole secret ID for authentication
- `--namespace`: Starting namespace (auto-detected if not provided)
  - For HCP Vault: defaults to "admin"
  - For self-hosted: defaults to root namespace
- `--output`: Output file path (default: scan_results.json)
- `--format`: Output format - "json" or "summary" (default: json)
- `--timeout`: Request timeout in seconds (default: 30)
- `--no-verify-ssl`: Disable SSL certificate verification

## Namespace Auto-Detection

The scanner automatically detects the appropriate starting namespace:
- **HCP Vault Dedicated**: Uses "admin" namespace by default
- **Self-hosted Vault**: Uses root namespace by default

You can override this behavior by explicitly providing the `--namespace` parameter.

## Output Format

### JSON Format

The scanner outputs a comprehensive JSON file with all collected data:

```json
{
  "vault_info": {
    "initialized": true,
    "sealed": false,
    "version": "1.15.0",
    "cluster_name": "vault-cluster",
    ...
  },
  "users": [...],
  "roles": [...],
  "policies": [...],
  "groups": [...],
  "namespaces": [...],
  "secrets": [...],
  "permissions": [...]
}
```

### Summary Format

When using `--format summary`, the scanner prints a quick overview:

```
=== Vault Scan Summary ===
Vault Version: 1.15.0
Users: 25
Roles: 10
Policies: 15
Groups: 5
Namespaces: 3
Secrets: 150
Permissions: 30
```

## Required Vault Permissions

The AppRole used for scanning needs the following permissions (example policy):

```hcl
# Read system health and status
path "sys/health" {
  capabilities = ["read"]
}

path "sys/leader" {
  capabilities = ["read"]
}

# Read auth methods and users
path "auth/userpass/users" {
  capabilities = ["list"]
}
path "auth/userpass/users/*" {
  capabilities = ["read"]
}

# Read policies
path "sys/policies/acl/*" {
  capabilities = ["list", "read"]
}

# Read AppRole roles
path "auth/approle/role" {
  capabilities = ["list"]
}
path "auth/approle/role/*" {
  capabilities = ["read"]
}

# Read identity groups
path "identity/group" {
  capabilities = ["list"]
}
path "identity/group/*" {
  capabilities = ["read"]
}

# Read namespaces
path "sys/namespaces" {
  capabilities = ["list", "read"]
}
path "sys/namespaces/*" {
  capabilities = ["list", "read"]
}

# Read secrets metadata (KVv2 example)
path "secret/metadata/*" {
  capabilities = ["list", "read"]
}
```

## Limitations

1. **User scanning**: Currently only supports the userpass auth method. Other auth methods (LDAP, OIDC, etc.) would need additional implementation.

2. **Roles**: Only scans AppRole roles. Other role types (AWS, Kubernetes, etc.) would need additional implementation.

3. **Secrets**: Only scans KVv2 secrets engine metadata. Other secret engines would need additional implementation.

4. **No secret values**: The scanner only retrieves metadata about secrets, not the actual secret values.

## Security Considerations

- Store your AppRole credentials securely
- Use the least privileged policy necessary for scanning
- The scanner only reads metadata, not secret values
- Consider using short-lived secret IDs that expire after use

## Example: Setting Up Scanner Credentials

1. Create the read-only policy (use the provided `setup-fabrix-read.sh` script)
2. Generate AppRole credentials:
   ```bash
   vault read auth/approle/role/fabrix-read/role-id
   vault write -f auth/approle/role/fabrix-read/secret-id
   ```
3. Use the generated role-id and secret-id with the scanner

## Troubleshooting

### Authentication Errors
- Verify your role-id and secret-id are correct
- Check that the AppRole is enabled at the expected path
- Ensure you're using the correct namespace

### Permission Errors
- Review the policy attached to your AppRole
- Ensure the policy has the necessary read/list permissions
- Check namespace-specific permissions

### SSL Errors
- Use `--no-verify-ssl` for self-signed certificates (not recommended for production)
- Ensure your Vault certificate is properly configured

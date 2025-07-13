# Airbyte Source Connector for HashiCorp Vault

This is an Airbyte source connector for HashiCorp Vault that allows you to sync various Vault resources and configurations.

## Features

The connector provides the following streams:

1. **vault** - General information about the Vault instance
2. **users** - User entities and userpass auth method users
3. **roles** - Roles from various auth methods (AppRole, Kubernetes, AWS, etc.)
4. **policies** - ACL, RGP, and EGP policies
5. **groups** - Identity groups (internal and external)
6. **namespaces** - Namespaces (recursively scanned, Enterprise feature)
7. **secrets** - Secret paths (recursively scanned, names only without values)
8. **permissions** - Permission mappings for users and groups based on policies
9. **secrets_engines** - Information about mounted secrets engines
10. **mfa_config** - MFA configuration across the system

## Configuration

The connector uses AppRole authentication and requires the following parameters:

- **vault_url** (required): The URL of your HashiCorp Vault instance
- **role_id** (required): The Role ID for AppRole authentication
- **secret_id** (required): The Secret ID for AppRole authentication
- **namespace** (optional): Starting namespace (use 'admin' for HCP Vault Dedicated, 'root' for non-HCP, or leave empty)
- **verify_ssl** (optional): Whether to verify SSL certificates (default: true)

### Example Configuration

```json
{
  "vault_url": "https://vault.example.com:8200",
  "role_id": "your-role-id-here",
  "secret_id": "your-secret-id-here",
  "namespace": "admin",
  "verify_ssl": true
}
```

## Required Vault Permissions

The AppRole used by the connector needs appropriate permissions to read the various resources. Here's a sample policy:

```hcl
# Read vault health and system info
path "sys/health" {
  capabilities = ["read"]
}

path "sys/license/status" {
  capabilities = ["read"]
}

path "sys/ha-status" {
  capabilities = ["read"]
}

path "sys/init" {
  capabilities = ["read"]
}

# List and read auth methods
path "sys/auth" {
  capabilities = ["read"]
}

path "auth/+/users/*" {
  capabilities = ["read", "list"]
}

path "auth/+/role/*" {
  capabilities = ["read", "list"]
}

# List and read identity entities and groups
path "identity/entity/*" {
  capabilities = ["read", "list"]
}

path "identity/group/*" {
  capabilities = ["read", "list"]
}

# List and read policies
path "sys/policies/*" {
  capabilities = ["read", "list"]
}

# List namespaces (Enterprise)
path "sys/namespaces/*" {
  capabilities = ["read", "list"]
}

# List and read mounts
path "sys/mounts" {
  capabilities = ["read"]
}

path "sys/mounts/*" {
  capabilities = ["read"]
}

# List secrets (adjust based on your secret engines)
path "+/metadata/*" {
  capabilities = ["list", "read"]
}

path "+/*" {
  capabilities = ["list"]
}

# MFA configuration
path "identity/mfa/*" {
  capabilities = ["read", "list"]
}

path "auth/+/mfa_config" {
  capabilities = ["read"]
}

path "auth/+/duo/config" {
  capabilities = ["read"]
}
```

## Usage

### Standalone Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create configuration:
   ```bash
   cp secrets/config.json.example secrets/config.json
   # Edit secrets/config.json with your credentials
   ```

3. Test connection:
   ```bash
   python main.py check --config secrets/config.json
   ```

4. Discover schema:
   ```bash
   python main.py discover --config secrets/config.json
   ```

5. Read data:
   ```bash
   python main.py read --config secrets/config.json --catalog configured_catalog.json
   ```

### Docker Usage

1. Build the image:
   ```bash
   docker build -t airbyte/source-hashicorp-vault:latest .
   ```

2. Run the connector:
   ```bash
   docker run --rm -v $(pwd)/secrets:/secrets airbyte/source-hashicorp-vault:latest \
     check --config /secrets/config.json
   ```

## Development

### Testing

Run the test script to verify the connector works:

```bash
python test_connector.py
```

### Adding New Streams

To add a new stream:

1. Create a new file in `source_hashicorp_vault/streams/`
2. Inherit from `VaultBaseStream`
3. Implement the required methods
4. Add the stream to `source_hashicorp_vault/streams/__init__.py`
5. Add the stream to the `streams()` method in `source.py`

## Notes

- The connector only reads secret **paths**, not the actual secret values
- Some features (namespaces, RGP/EGP policies, Identity MFA) require Vault Enterprise
- The connector handles errors gracefully and will skip resources it doesn't have access to
- Recursive operations (namespaces, secrets) are performed carefully to avoid overwhelming the Vault server

## License

MIT

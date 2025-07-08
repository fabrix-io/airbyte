# 1Password Source

This is the repository for the 1Password source connector, written in Python.
For information about how to use this connector within Airbyte, see [the documentation](https://docs.airbyte.com/integrations/sources/onepassword).

## Local development

### Prerequisites

- Python ~=3.10
- Poetry
- 1Password CLI (`op`) installed and available in PATH

The 1Password CLI can be installed following the instructions at: https://developer.1password.com/docs/cli/get-started

### Installing the connector

From this connector directory, run:
```bash
poetry install --with dev
```

### Create credentials

You'll need a 1Password service account token to authenticate. You can create one by following the instructions at:
https://developer.1password.com/docs/service-accounts/

### Running the connector

```bash
poetry run source-onepassword spec
poetry run source-onepassword check --config secrets/config.json
poetry run source-onepassword discover --config secrets/config.json
poetry run source-onepassword read --config secrets/config.json --catalog sample_catalog.json
```

### Running unit tests

To run unit tests:
```bash
poetry run pytest unit_tests
```

### Building the docker image

```bash
docker build . -t airbyte/source-onepassword:dev
```

## Configuration

The connector requires the following configuration:

- `access_token`: The 1Password service account token for authentication

Example configuration:
```json
{
  "access_token": "your-service-account-token"
}
```

## Supported Streams

This connector supports the following streams:

- **Account**: Basic account information
- **Vaults**: List of all vaults in the account
- **Groups**: User groups
- **Service Accounts**: Service accounts
- **Users**: User accounts
- **Items**: All items across all vaults (passwords, secure notes, etc.)
- **Group Memberships**: Mapping of users to groups
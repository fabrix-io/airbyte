#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, List, Mapping, Tuple

import hvac
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http.auth import NoAuth

from .streams import (
    GroupsStream,
    MFAConfigStream,
    NamespacesStream,
    PermissionsStream,
    PoliciesStream,
    RolesStream,
    SecretsEnginesStream,
    SecretsStream,
    UsersStream,
    VaultStream,
)


class SourceHashicorpVault(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        Check connection to HashiCorp Vault using AppRole authentication
        """
        try:
            client = self._get_vault_client(config)
            
            # Check if the client is authenticated
            if not client.is_authenticated():
                return False, "Failed to authenticate with Vault using provided credentials"
            
            # Try to read the token info to verify connection
            try:
                client.auth.token.lookup_self()
            except Exception as e:
                return False, f"Failed to verify authentication: {str(e)}"
            
            return True, None
        except Exception as e:
            return False, f"Failed to connect to Vault: {str(e)}"
    
    def _get_vault_client(self, config: Mapping[str, Any]) -> hvac.Client:
        """
        Create and authenticate a Vault client
        """
        client = hvac.Client(
            url=config["vault_url"],
            verify=config.get("verify_ssl", True),
            namespace=config.get("namespace", None)
        )
        
        # Authenticate using AppRole
        response = client.auth.approle.login(
            role_id=config["role_id"],
            secret_id=config["secret_id"]
        )
        
        # Set the token from the authentication response
        client.token = response["auth"]["client_token"]
        
        return client

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        Return the list of streams to sync
        """
        vault_client = self._get_vault_client(config)
        
        return [
            VaultStream(vault_client=vault_client, config=config),
            UsersStream(vault_client=vault_client, config=config),
            RolesStream(vault_client=vault_client, config=config),
            PoliciesStream(vault_client=vault_client, config=config),
            GroupsStream(vault_client=vault_client, config=config),
            NamespacesStream(vault_client=vault_client, config=config),
            SecretsStream(vault_client=vault_client, config=config),
            PermissionsStream(vault_client=vault_client, config=config),
            SecretsEnginesStream(vault_client=vault_client, config=config),
            MFAConfigStream(vault_client=vault_client, config=config),
        ]
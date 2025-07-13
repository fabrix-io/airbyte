#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from abc import ABC
from typing import Any, Iterable, Mapping, MutableMapping, Optional

import hvac
import requests
from airbyte_cdk.sources.streams import Stream


class VaultBaseStream(Stream, ABC):
    """
    Base stream for HashiCorp Vault
    """
    
    def __init__(self, vault_client: hvac.Client, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.vault_client = vault_client
        self.config = config
        self._session = requests.Session()
        self._session.headers.update({
            "X-Vault-Token": vault_client.token,
        })
        if vault_client.namespace:
            self._session.headers.update({
                "X-Vault-Namespace": vault_client.namespace,
            })
    
    @property
    def primary_key(self) -> Optional[str]:
        """Override in subclasses if needed"""
        return None
    
    def get_json_schema(self) -> Mapping[str, Any]:
        """
        Return the JSON schema for the stream.
        Override in subclasses to provide specific schema.
        """
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": True,
        }
    
    def _make_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Make a request to the Vault API
        """
        url = f"{self.vault_client.url}/v1/{path.lstrip('/')}"
        response = self._session.request(
            method=method,
            url=url,
            verify=self.config.get("verify_ssl", True),
            **kwargs
        )
        response.raise_for_status()
        return response
    
    def _list_request(self, path: str) -> Optional[list]:
        """
        Make a LIST request to the Vault API
        """
        try:
            response = self._make_request("LIST", path)
            data = response.json()
            return data.get("data", {}).get("keys", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
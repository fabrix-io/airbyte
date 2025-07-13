#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class VaultStream(VaultBaseStream):
    """
    Stream for retrieving general Vault information
    """
    
    @property
    def name(self) -> str:
        return "vault"
    
    @property
    def primary_key(self) -> str:
        return "cluster_id"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "cluster_id": {"type": ["string", "null"]},
                "cluster_name": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "is_self_hosted": {"type": ["boolean", "null"]},
                "license": {"type": ["object", "null"]},
                "health": {"type": ["object", "null"]},
                "high_availability_enabled": {"type": ["boolean", "null"]},
                "raft_storage": {"type": ["boolean", "null"]},
                "performance_standby": {"type": ["boolean", "null"]},
                "initialization_status": {"type": ["object", "null"]},
                "namespace": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        }
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read Vault general information
        """
        vault_info = {}
        
        try:
            # Get health status
            health_response = self._make_request("GET", "sys/health")
            vault_info["health"] = health_response.json()
            vault_info["cluster_id"] = vault_info["health"].get("cluster_id")
            vault_info["cluster_name"] = vault_info["health"].get("cluster_name")
            vault_info["version"] = vault_info["health"].get("version")
        except Exception as e:
            self.logger.warning(f"Failed to get health info: {str(e)}")
        
        try:
            # Get license info
            license_response = self._make_request("GET", "sys/license/status")
            vault_info["license"] = license_response.json().get("data", {})
        except Exception as e:
            self.logger.debug(f"Failed to get license info (may be OSS): {str(e)}")
        
        try:
            # Get HA status
            ha_response = self._make_request("GET", "sys/ha-status")
            ha_data = ha_response.json()
            vault_info["high_availability_enabled"] = True
            vault_info["raft_storage"] = ha_data.get("data", {}).get("raft", {}) is not None
        except Exception as e:
            vault_info["high_availability_enabled"] = False
            self.logger.debug(f"Failed to get HA status: {str(e)}")
        
        try:
            # Get initialization status
            init_response = self._make_request("GET", "sys/init")
            vault_info["initialization_status"] = init_response.json()
        except Exception as e:
            self.logger.debug(f"Failed to get initialization status: {str(e)}")
        
        # Add namespace info
        vault_info["namespace"] = self.vault_client.namespace or "root"
        vault_info["is_self_hosted"] = not (
            self.vault_client.url.startswith("https://") and 
            ".hashicorp.cloud" in self.vault_client.url
        )
        
        yield vault_info
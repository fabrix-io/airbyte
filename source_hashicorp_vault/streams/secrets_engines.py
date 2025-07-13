#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class SecretsEnginesStream(VaultBaseStream):
    """
    Stream for retrieving Vault secrets engines
    """
    
    @property
    def name(self) -> str:
        return "secrets_engines"
    
    @property
    def primary_key(self) -> str:
        return "path"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "type": {"type": "string"},
                "description": {"type": ["string", "null"]},
                "accessor": {"type": ["string", "null"]},
                "config": {"type": ["object", "null"]},
                "options": {"type": ["object", "null"]},
                "local": {"type": ["boolean", "null"]},
                "seal_wrap": {"type": ["boolean", "null"]},
                "external_entropy_access": {"type": ["boolean", "null"]},
                "namespace": {"type": ["string", "null"]},
                "running_version": {"type": ["string", "null"]},
                "running_sha256": {"type": ["string", "null"]},
                "deprecation_status": {"type": ["string", "null"]},
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
        Read all mounted secrets engines
        """
        try:
            mounts_response = self._make_request("GET", "sys/mounts")
            mounts_data = mounts_response.json()
            
            for mount_path, mount_info in mounts_data.get("data", {}).items():
                # Skip system mounts
                if mount_path.startswith("sys/"):
                    continue
                
                engine_info = {
                    "path": mount_path,
                    "type": mount_info.get("type"),
                    "description": mount_info.get("description"),
                    "accessor": mount_info.get("accessor"),
                    "config": mount_info.get("config", {}),
                    "options": mount_info.get("options", {}),
                    "local": mount_info.get("local", False),
                    "seal_wrap": mount_info.get("seal_wrap", False),
                    "external_entropy_access": mount_info.get("external_entropy_access", False),
                    "namespace": self.vault_client.namespace or "root",
                    "running_version": mount_info.get("running_version"),
                    "running_sha256": mount_info.get("running_sha256"),
                    "deprecation_status": mount_info.get("deprecation_status"),
                }
                
                # Get additional configuration for specific engine types
                engine_type = mount_info.get("type", "")
                
                if engine_type == "database":
                    # Try to list database connections
                    try:
                        db_configs = self._list_request(f"{mount_path}config")
                        engine_info["database_connections"] = db_configs or []
                    except Exception as e:
                        self.logger.debug(f"Failed to list database connections: {str(e)}")
                
                elif engine_type == "pki":
                    # Try to get PKI configuration
                    try:
                        # List certificate authorities
                        issuers = self._list_request(f"{mount_path}issuers")
                        engine_info["pki_issuers"] = issuers or []
                        
                        # List roles
                        roles = self._list_request(f"{mount_path}roles")
                        engine_info["pki_roles"] = roles or []
                    except Exception as e:
                        self.logger.debug(f"Failed to get PKI info: {str(e)}")
                
                elif engine_type == "aws":
                    # Try to get AWS configuration
                    try:
                        # Check if configured
                        aws_config_response = self._make_request("GET", f"{mount_path}config/root")
                        engine_info["aws_configured"] = True
                        
                        # List roles
                        roles = self._list_request(f"{mount_path}roles")
                        engine_info["aws_roles"] = roles or []
                    except Exception as e:
                        engine_info["aws_configured"] = False
                        self.logger.debug(f"Failed to get AWS config: {str(e)}")
                
                elif engine_type == "ssh":
                    # Try to get SSH configuration
                    try:
                        # List SSH roles
                        roles = self._list_request(f"{mount_path}roles")
                        engine_info["ssh_roles"] = roles or []
                        
                        # Check if CA is configured
                        try:
                            ca_response = self._make_request("GET", f"{mount_path}config/ca")
                            engine_info["ssh_ca_configured"] = True
                        except Exception:
                            engine_info["ssh_ca_configured"] = False
                    except Exception as e:
                        self.logger.debug(f"Failed to get SSH info: {str(e)}")
                
                elif engine_type in ["kv", "kv-v2"]:
                    # Get KV specific info
                    kv_version = mount_info.get("options", {}).get("version", "1")
                    engine_info["kv_version"] = kv_version
                    
                    if kv_version == "2":
                        try:
                            # Get KV v2 configuration
                            config_response = self._make_request("GET", f"{mount_path}config")
                            engine_info["kv_config"] = config_response.json().get("data", {})
                        except Exception as e:
                            self.logger.debug(f"Failed to get KV config: {str(e)}")
                
                yield engine_info
                
        except Exception as e:
            self.logger.error(f"Failed to list secrets engines: {str(e)}")
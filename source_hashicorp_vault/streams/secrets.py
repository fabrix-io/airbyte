#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class SecretsStream(VaultBaseStream):
    """
    Stream for retrieving Vault secrets (paths only, no values)
    """
    
    @property
    def name(self) -> str:
        return "secrets"
    
    @property
    def primary_key(self) -> str:
        return "full_path"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "full_path": {"type": "string"},
                "path": {"type": "string"},
                "name": {"type": "string"},
                "mount": {"type": "string"},
                "mount_type": {"type": "string"},
                "is_folder": {"type": "boolean"},
                "namespace": {"type": ["string", "null"]},
                "version": {"type": ["integer", "null"]},
                "created_time": {"type": ["string", "null"]},
                "updated_time": {"type": ["string", "null"]},
                "deletion_time": {"type": ["string", "null"]},
                "destroyed": {"type": ["boolean", "null"]},
            },
            "additionalProperties": True,
        }
    
    def _get_secret_mounts(self) -> list:
        """
        Get all secret engine mounts
        """
        mounts = []
        try:
            mounts_response = self._make_request("GET", "sys/mounts")
            mounts_data = mounts_response.json().get("data", {})
            
            for mount_path, mount_info in mounts_data.items():
                # Only include secret engines (not auth methods or system mounts)
                mount_type = mount_info.get("type", "")
                if mount_type in ["kv", "kv-v2", "generic", "cubbyhole", "transit", "pki", "database"]:
                    mounts.append({
                        "path": mount_path,
                        "type": mount_type,
                        "version": mount_info.get("options", {}).get("version", "1") if mount_type in ["kv", "kv-v2"] else None,
                        "description": mount_info.get("description", ""),
                    })
        except Exception as e:
            self.logger.warning(f"Failed to get secret mounts: {str(e)}")
        
        return mounts
    
    def _list_secrets_recursive(self, mount: dict, path: str = "") -> Iterable[Mapping[str, Any]]:
        """
        Recursively list secrets in a mount
        """
        mount_path = mount["path"]
        mount_type = mount["type"]
        
        # Build the full path for listing
        if mount_type == "kv-v2" or (mount_type == "kv" and mount.get("version") == "2"):
            # KV v2 uses metadata path for listing
            list_path = f"{mount_path}metadata/{path}"
        else:
            # KV v1 and other secret engines
            list_path = f"{mount_path}{path}"
        
        try:
            items = self._list_request(list_path)
            if items:
                for item in items:
                    is_folder = item.endswith('/')
                    item_name = item.rstrip('/')
                    
                    # Construct the full path
                    if path:
                        item_path = f"{path}{item_name}"
                    else:
                        item_path = item_name
                    
                    full_path = f"{mount_path}{item_path}"
                    
                    secret_info = {
                        "full_path": full_path,
                        "path": item_path,
                        "name": item_name,
                        "mount": mount_path.rstrip('/'),
                        "mount_type": mount_type,
                        "is_folder": is_folder,
                        "namespace": self.vault_client.namespace or "root",
                    }
                    
                    # For KV v2, try to get metadata if it's not a folder
                    if not is_folder and (mount_type == "kv-v2" or (mount_type == "kv" and mount.get("version") == "2")):
                        try:
                            metadata_response = self._make_request("GET", f"{mount_path}metadata/{item_path}")
                            metadata = metadata_response.json().get("data", {})
                            secret_info.update({
                                "version": metadata.get("current_version"),
                                "created_time": metadata.get("created_time"),
                                "updated_time": metadata.get("updated_time"),
                                "deletion_time": metadata.get("deletion_time"),
                                "destroyed": metadata.get("destroyed", False),
                            })
                        except Exception as e:
                            self.logger.debug(f"Failed to get metadata for {full_path}: {str(e)}")
                    
                    yield secret_info
                    
                    # If it's a folder, recurse into it
                    if is_folder:
                        yield from self._list_secrets_recursive(mount, f"{item_path}/")
                        
        except Exception as e:
            if "404" not in str(e):  # Ignore 404s as they might just be empty paths
                self.logger.debug(f"Failed to list secrets at {list_path}: {str(e)}")
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read secret paths from all secret engine mounts
        """
        # Get all secret engine mounts
        mounts = self._get_secret_mounts()
        
        # For each mount, recursively list all secrets
        for mount in mounts:
            try:
                yield from self._list_secrets_recursive(mount)
            except Exception as e:
                self.logger.warning(f"Failed to list secrets in mount {mount['path']}: {str(e)}")
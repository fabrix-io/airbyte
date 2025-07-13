#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class NamespacesStream(VaultBaseStream):
    """
    Stream for retrieving Vault namespaces recursively
    """
    
    @property
    def name(self) -> str:
        return "namespaces"
    
    @property
    def primary_key(self) -> str:
        return "path"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "path": {"type": "string"},
                "name": {"type": "string"},
                "parent_namespace": {"type": ["string", "null"]},
                "custom_metadata": {"type": ["object", "null"]},
                "namespace_id": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        }
    
    def _get_namespaces_recursive(self, parent_path: str = "") -> Iterable[Mapping[str, Any]]:
        """
        Recursively get all namespaces
        """
        # Save current namespace
        original_namespace = self.vault_client.namespace
        
        try:
            # Switch to the parent namespace
            if parent_path:
                self.vault_client.namespace = parent_path
                # Update session headers
                self._session.headers.update({
                    "X-Vault-Namespace": parent_path,
                })
            
            # List namespaces in current context
            try:
                namespaces = self._list_request("sys/namespaces")
                if namespaces:
                    for namespace_name in namespaces:
                        # Remove trailing slash if present
                        namespace_name = namespace_name.rstrip('/')
                        
                        try:
                            # Get namespace details
                            ns_response = self._make_request("GET", f"sys/namespaces/{namespace_name}")
                            ns_data = ns_response.json().get("data", {})
                            
                            # Construct full path
                            if parent_path:
                                full_path = f"{parent_path}{namespace_name}/"
                            else:
                                full_path = f"{namespace_name}/"
                            
                            yield {
                                "id": ns_data.get("id", full_path),
                                "path": full_path,
                                "name": namespace_name,
                                "parent_namespace": parent_path or None,
                                "custom_metadata": ns_data.get("custom_metadata", {}),
                                "namespace_id": ns_data.get("namespace_id"),
                            }
                            
                            # Recursively get child namespaces
                            yield from self._get_namespaces_recursive(full_path)
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to get namespace {namespace_name}: {str(e)}")
            except Exception as e:
                self.logger.debug(f"Failed to list namespaces in {parent_path or 'root'}: {str(e)}")
                
        finally:
            # Restore original namespace
            self.vault_client.namespace = original_namespace
            if original_namespace:
                self._session.headers.update({
                    "X-Vault-Namespace": original_namespace,
                })
            else:
                self._session.headers.pop("X-Vault-Namespace", None)
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read Vault namespaces recursively
        """
        # Check if namespaces are supported (Enterprise feature)
        try:
            # Try to list namespaces to see if the feature is available
            test_response = self._make_request("LIST", "sys/namespaces")
            
            # If we get here, namespaces are supported
            # Start from the current namespace (which could be root, admin, or custom)
            starting_namespace = self.vault_client.namespace or ""
            
            # Include the current namespace itself
            if starting_namespace:
                yield {
                    "id": starting_namespace.rstrip('/'),
                    "path": starting_namespace if starting_namespace.endswith('/') else f"{starting_namespace}/",
                    "name": starting_namespace.rstrip('/').split('/')[-1],
                    "parent_namespace": '/'.join(starting_namespace.rstrip('/').split('/')[:-1]) + '/' if '/' in starting_namespace else None,
                    "namespace_id": starting_namespace.rstrip('/'),
                }
            
            # Get all child namespaces recursively
            yield from self._get_namespaces_recursive(starting_namespace)
            
        except Exception as e:
            if "404" in str(e) or "path is unsupported" in str(e):
                self.logger.info("Namespaces are not supported (likely using Vault OSS)")
            else:
                self.logger.warning(f"Failed to list namespaces: {str(e)}")
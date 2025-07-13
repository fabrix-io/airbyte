#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class PermissionsStream(VaultBaseStream):
    """
    Stream for retrieving permissions for users and groups based on policy assignments
    """
    
    @property
    def name(self) -> str:
        return "permissions"
    
    @property
    def primary_key(self) -> str:
        return "id"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "entity_type": {"type": "string"},  # "user" or "group"
                "entity_id": {"type": "string"},
                "entity_name": {"type": ["string", "null"]},
                "policies": {"type": "array", "items": {"type": "string"}},
                "inherited_policies": {"type": "array", "items": {"type": "string"}},
                "effective_policies": {"type": "array", "items": {"type": "string"}},
                "permissions": {"type": "array", "items": {"type": "object"}},
                "namespace": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        }
    
    def _get_policy_permissions(self, policy_name: str) -> list:
        """
        Extract permissions from a policy
        """
        permissions = []
        try:
            policy_response = self._make_request("GET", f"sys/policies/acl/{policy_name}")
            policy_data = policy_response.json()
            policy_text = policy_data.get("data", {}).get("policy", "")
            
            # Parse the policy to extract paths and capabilities
            lines = policy_text.split('\n')
            current_path = None
            current_capabilities = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('path'):
                    # Save previous path if exists
                    if current_path:
                        permissions.append({
                            "policy": policy_name,
                            "path": current_path,
                            "capabilities": current_capabilities
                        })
                    # Extract new path
                    parts = line.split('"')
                    if len(parts) >= 2:
                        current_path = parts[1]
                        current_capabilities = []
                elif line.startswith('capabilities') and '=' in line:
                    # Extract capabilities
                    cap_part = line.split('=')[1].strip()
                    if cap_part.startswith('[') and cap_part.endswith(']'):
                        caps = cap_part[1:-1].split(',')
                        current_capabilities = [cap.strip().strip('"') for cap in caps]
            
            # Save last path if exists
            if current_path:
                permissions.append({
                    "policy": policy_name,
                    "path": current_path,
                    "capabilities": current_capabilities
                })
        except Exception as e:
            self.logger.debug(f"Failed to get policy permissions for {policy_name}: {str(e)}")
        
        return permissions
    
    def _get_user_permissions(self) -> Iterable[Mapping[str, Any]]:
        """
        Get permissions for users (entities)
        """
        try:
            entities = self._list_request("identity/entity/id")
            if entities:
                for entity_id in entities:
                    try:
                        entity_response = self._make_request("GET", f"identity/entity/id/{entity_id}")
                        entity_data = entity_response.json().get("data", {})
                        
                        # Direct policies
                        direct_policies = entity_data.get("policies", [])
                        
                        # Get group policies
                        group_policies = []
                        group_ids = entity_data.get("group_ids", [])
                        for group_id in group_ids:
                            try:
                                group_response = self._make_request("GET", f"identity/group/id/{group_id}")
                                group_data = group_response.json().get("data", {})
                                group_policies.extend(group_data.get("policies", []))
                            except Exception as e:
                                self.logger.debug(f"Failed to get group {group_id}: {str(e)}")
                        
                        # Combine all policies
                        all_policies = list(set(direct_policies + group_policies))
                        
                        # Get permissions for each policy
                        all_permissions = []
                        for policy in all_policies:
                            all_permissions.extend(self._get_policy_permissions(policy))
                        
                        yield {
                            "id": f"user-{entity_id}",
                            "entity_type": "user",
                            "entity_id": entity_id,
                            "entity_name": entity_data.get("name"),
                            "policies": direct_policies,
                            "inherited_policies": group_policies,
                            "effective_policies": all_policies,
                            "permissions": all_permissions,
                            "namespace": entity_data.get("namespace_id", self.vault_client.namespace or "root"),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get permissions for entity {entity_id}: {str(e)}")
        except Exception as e:
            self.logger.warning(f"Failed to list entities for permissions: {str(e)}")
    
    def _get_group_permissions(self) -> Iterable[Mapping[str, Any]]:
        """
        Get permissions for groups
        """
        try:
            groups = self._list_request("identity/group/id")
            if groups:
                for group_id in groups:
                    try:
                        group_response = self._make_request("GET", f"identity/group/id/{group_id}")
                        group_data = group_response.json().get("data", {})
                        
                        # Direct policies
                        direct_policies = group_data.get("policies", [])
                        
                        # Get parent group policies
                        parent_policies = []
                        parent_group_ids = group_data.get("parent_group_ids", [])
                        for parent_id in parent_group_ids:
                            try:
                                parent_response = self._make_request("GET", f"identity/group/id/{parent_id}")
                                parent_data = parent_response.json().get("data", {})
                                parent_policies.extend(parent_data.get("policies", []))
                            except Exception as e:
                                self.logger.debug(f"Failed to get parent group {parent_id}: {str(e)}")
                        
                        # Combine all policies
                        all_policies = list(set(direct_policies + parent_policies))
                        
                        # Get permissions for each policy
                        all_permissions = []
                        for policy in all_policies:
                            all_permissions.extend(self._get_policy_permissions(policy))
                        
                        yield {
                            "id": f"group-{group_id}",
                            "entity_type": "group",
                            "entity_id": group_id,
                            "entity_name": group_data.get("name"),
                            "policies": direct_policies,
                            "inherited_policies": parent_policies,
                            "effective_policies": all_policies,
                            "permissions": all_permissions,
                            "namespace": group_data.get("namespace_id", self.vault_client.namespace or "root"),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get permissions for group {group_id}: {str(e)}")
        except Exception as e:
            self.logger.warning(f"Failed to list groups for permissions: {str(e)}")
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read permissions for users and groups
        """
        # Get user permissions
        yield from self._get_user_permissions()
        
        # Get group permissions
        yield from self._get_group_permissions()
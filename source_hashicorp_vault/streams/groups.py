#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class GroupsStream(VaultBaseStream):
    """
    Stream for retrieving Vault identity groups
    """
    
    @property
    def name(self) -> str:
        return "groups"
    
    @property
    def primary_key(self) -> str:
        return "id"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "type": {"type": "string"},  # "internal" or "external"
                "policies": {"type": "array", "items": {"type": "string"}},
                "member_entity_ids": {"type": "array", "items": {"type": "string"}},
                "member_group_ids": {"type": "array", "items": {"type": "string"}},
                "parent_group_ids": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": ["object", "null"]},
                "creation_time": {"type": ["string", "null"]},
                "last_update_time": {"type": ["string", "null"]},
                "alias": {"type": ["object", "null"]},
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
        Read Vault identity groups
        """
        # Get internal groups by ID
        try:
            groups = self._list_request("identity/group/id")
            if groups:
                for group_id in groups:
                    try:
                        group_response = self._make_request("GET", f"identity/group/id/{group_id}")
                        group_data = group_response.json().get("data", {})
                        
                        yield {
                            "id": group_id,
                            "name": group_data.get("name"),
                            "type": group_data.get("type", "internal"),
                            "policies": group_data.get("policies", []),
                            "member_entity_ids": group_data.get("member_entity_ids", []),
                            "member_group_ids": group_data.get("member_group_ids", []),
                            "parent_group_ids": group_data.get("parent_group_ids", []),
                            "metadata": group_data.get("metadata", {}),
                            "creation_time": group_data.get("creation_time"),
                            "last_update_time": group_data.get("last_update_time"),
                            "alias": group_data.get("alias"),
                            "namespace": group_data.get("namespace_id", self.vault_client.namespace or "root"),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get group {group_id}: {str(e)}")
        except Exception as e:
            self.logger.warning(f"Failed to list identity groups: {str(e)}")
        
        # Get groups by name (alternative approach)
        try:
            groups_by_name = self._list_request("identity/group/name")
            if groups_by_name:
                for group_name in groups_by_name:
                    try:
                        group_response = self._make_request("GET", f"identity/group/name/{group_name}")
                        group_data = group_response.json().get("data", {})
                        
                        # Skip if we already got this group by ID
                        group_id = group_data.get("id")
                        if group_id and group_id in (groups or []):
                            continue
                        
                        yield {
                            "id": group_id or f"name-{group_name}",
                            "name": group_name,
                            "type": group_data.get("type", "internal"),
                            "policies": group_data.get("policies", []),
                            "member_entity_ids": group_data.get("member_entity_ids", []),
                            "member_group_ids": group_data.get("member_group_ids", []),
                            "parent_group_ids": group_data.get("parent_group_ids", []),
                            "metadata": group_data.get("metadata", {}),
                            "creation_time": group_data.get("creation_time"),
                            "last_update_time": group_data.get("last_update_time"),
                            "alias": group_data.get("alias"),
                            "namespace": group_data.get("namespace_id", self.vault_client.namespace or "root"),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get group by name {group_name}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list groups by name: {str(e)}")
#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class UsersStream(VaultBaseStream):
    """
    Stream for retrieving Vault users (from userpass auth method and identity entities)
    """
    
    @property
    def name(self) -> str:
        return "users"
    
    @property
    def primary_key(self) -> str:
        return "id"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "username": {"type": ["string", "null"]},
                "type": {"type": "string"},  # "userpass" or "entity"
                "entity_id": {"type": ["string", "null"]},
                "policies": {"type": "array", "items": {"type": "string"}},
                "token_policies": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": ["object", "null"]},
                "aliases": {"type": "array", "items": {"type": "object"}},
                "group_ids": {"type": "array", "items": {"type": "string"}},
                "namespace": {"type": ["string", "null"]},
                "creation_time": {"type": ["string", "null"]},
                "last_update_time": {"type": ["string", "null"]},
                "disabled": {"type": ["boolean", "null"]},
                "mfa_secrets": {"type": ["object", "null"]},
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
        Read users from both userpass auth method and identity entities
        """
        # Get users from userpass auth method
        try:
            userpass_users = self._list_request("auth/userpass/users")
            if userpass_users:
                for username in userpass_users:
                    try:
                        user_response = self._make_request("GET", f"auth/userpass/users/{username}")
                        user_data = user_response.json().get("data", {})
                        yield {
                            "id": f"userpass-{username}",
                            "username": username,
                            "type": "userpass",
                            "policies": user_data.get("policies", []),
                            "token_policies": user_data.get("token_policies", []),
                            "metadata": user_data.get("metadata", {}),
                            "namespace": self.vault_client.namespace or "root",
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get userpass user {username}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list userpass users (auth method may not be enabled): {str(e)}")
        
        # Get identity entities
        try:
            entities = self._list_request("identity/entity/id")
            if entities:
                for entity_id in entities:
                    try:
                        entity_response = self._make_request("GET", f"identity/entity/id/{entity_id}")
                        entity_data = entity_response.json().get("data", {})
                        
                        # Extract usernames from aliases
                        username = None
                        if entity_data.get("aliases"):
                            for alias in entity_data["aliases"]:
                                if alias.get("mount_type") == "userpass":
                                    username = alias.get("name")
                                    break
                        
                        yield {
                            "id": entity_id,
                            "username": username or entity_data.get("name"),
                            "type": "entity",
                            "entity_id": entity_id,
                            "policies": entity_data.get("policies", []),
                            "metadata": entity_data.get("metadata", {}),
                            "aliases": entity_data.get("aliases", []),
                            "group_ids": entity_data.get("group_ids", []),
                            "namespace": entity_data.get("namespace_id", self.vault_client.namespace or "root"),
                            "creation_time": entity_data.get("creation_time"),
                            "last_update_time": entity_data.get("last_update_time"),
                            "disabled": entity_data.get("disabled", False),
                            "mfa_secrets": entity_data.get("mfa_secrets", {}),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get entity {entity_id}: {str(e)}")
        except Exception as e:
            self.logger.warning(f"Failed to list identity entities: {str(e)}")
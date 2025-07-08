#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

import json
import subprocess
from typing import Any, Iterable, Mapping, Optional
from abc import ABC

from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.models import SyncMode


class OnePasswordStream(Stream, ABC):
    """
    Base stream class for all 1Password streams
    """
    
    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self._access_token = config.get("access_token")
    
    @property
    def primary_key(self) -> Optional[str]:
        return "id"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        """Return the JSON schema for this stream"""
        # Load schema from file
        schema_path = f"schemas/{self.name}.json"
        try:
            with open(f"source_onepassword/{schema_path}", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            # Return a basic schema if file not found
            return {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"}
                }
            }
    
    def _run_op_command(self, command: list) -> list:
        """
        Run a 1Password CLI command and return the JSON output
        """
        import os
        env = os.environ.copy()
        env["OP_SERVICE_ACCOUNT_TOKEN"] = str(self._access_token)
        
        try:
            result = subprocess.run(
                command + ["--format=json"],
                capture_output=True,
                text=True,
                env=env,
                check=True
            )
            
            output = result.stdout.strip()
            if not output:
                return []
                
            # Parse JSON output
            data = json.loads(output)
            
            # Ensure we always return a list
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                return []
                
        except subprocess.CalledProcessError as e:
            # Log error but continue
            print(f"Error running command {' '.join(command)}: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON output: {e}")
            return []
    
    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field: Optional[str] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """Read records from the stream"""
        return self._read_records()
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Implemented by subclasses to read specific records"""
        raise NotImplementedError


class AccountStream(OnePasswordStream):
    """Stream for 1Password account information"""
    
    @property
    def name(self) -> str:
        return "account"
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read account information"""
        records = self._run_op_command(["op", "account", "get"])
        for record in records:
            yield record


class VaultsStream(OnePasswordStream):
    """Stream for 1Password vaults"""
    
    @property
    def name(self) -> str:
        return "vaults"
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read all vaults"""
        records = self._run_op_command(["op", "vault", "list"])
        for record in records:
            yield record


class GroupsStream(OnePasswordStream):
    """Stream for 1Password groups"""
    
    @property
    def name(self) -> str:
        return "groups"
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read all groups"""
        records = self._run_op_command(["op", "group", "list"])
        for record in records:
            yield record


class ServiceAccountsStream(OnePasswordStream):
    """Stream for 1Password service accounts"""
    
    @property
    def name(self) -> str:
        return "service_accounts"
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read all service accounts"""
        records = self._run_op_command(["op", "service-account", "list"])
        for record in records:
            yield record


class UsersStream(OnePasswordStream):
    """Stream for 1Password users"""
    
    @property
    def name(self) -> str:
        return "users"
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read all users"""
        records = self._run_op_command(["op", "user", "list"])
        for record in records:
            yield record


class ItemsStream(OnePasswordStream):
    """Stream for 1Password items"""
    
    @property
    def name(self) -> str:
        return "items"
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read all items from all vaults"""
        # First get all vaults
        vaults = self._run_op_command(["op", "vault", "list"])
        
        for vault in vaults:
            vault_id = vault.get("id")
            if vault_id:
                # Get items from each vault
                items = self._run_op_command(["op", "item", "list", "--vault", vault_id])
                for item in items:
                    # Add vault information to each item
                    item["vault_id"] = vault_id
                    item["vault_name"] = vault.get("name", "")
                    yield item


class GroupMembershipsStream(OnePasswordStream):
    """Stream for 1Password group memberships"""
    
    @property
    def name(self) -> str:
        return "group_memberships"
    
    @property
    def primary_key(self) -> Optional[str]:
        # Composite key for group memberships
        return None
    
    def _read_records(self) -> Iterable[Mapping[str, Any]]:
        """Read all group memberships"""
        # First get all groups
        groups = self._run_op_command(["op", "group", "list"])
        
        for group in groups:
            group_id = group.get("id")
            group_name = group.get("name", "")
            
            if group_id:
                # Get members of each group
                members = self._run_op_command(["op", "group", "user", "list", group_id])
                
                for member in members:
                    # Create a membership record
                    membership = {
                        "group_id": group_id,
                        "group_name": group_name,
                        "user_id": member.get("id"),
                        "user_email": member.get("email", ""),
                        "user_name": member.get("name", ""),
                        "role": member.get("role", "member")
                    }
                    yield membership
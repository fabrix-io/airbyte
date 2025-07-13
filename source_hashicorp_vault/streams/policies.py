#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class PoliciesStream(VaultBaseStream):
    """
    Stream for retrieving Vault policies
    """
    
    @property
    def name(self) -> str:
        return "policies"
    
    @property
    def primary_key(self) -> str:
        return "name"
    
    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "policy": {"type": "string"},
                "type": {"type": "string"},  # "acl" or "rgp" or "egp"
                "namespace": {"type": ["string", "null"]},
                "paths": {"type": "array", "items": {"type": "object"}},
                "enforcement_level": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        }
    
    def _parse_policy_paths(self, policy_text: str) -> list:
        """
        Parse the policy text to extract paths and capabilities
        """
        paths = []
        lines = policy_text.split('\n')
        current_path = None
        current_capabilities = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('path'):
                # Save previous path if exists
                if current_path:
                    paths.append({
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
            paths.append({
                "path": current_path,
                "capabilities": current_capabilities
            })
        
        return paths
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read Vault policies
        """
        # Get ACL policies
        try:
            policies = self._list_request("sys/policies/acl")
            if policies:
                for policy_name in policies:
                    try:
                        policy_response = self._make_request("GET", f"sys/policies/acl/{policy_name}")
                        policy_data = policy_response.json()
                        policy_text = policy_data.get("data", {}).get("policy", "")
                        
                        yield {
                            "name": policy_name,
                            "policy": policy_text,
                            "type": "acl",
                            "namespace": self.vault_client.namespace or "root",
                            "paths": self._parse_policy_paths(policy_text),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get ACL policy {policy_name}: {str(e)}")
        except Exception as e:
            self.logger.warning(f"Failed to list ACL policies: {str(e)}")
        
        # Get RGP policies (Role Governing Policies)
        try:
            rgp_policies = self._list_request("sys/policies/rgp")
            if rgp_policies:
                for policy_name in rgp_policies:
                    try:
                        policy_response = self._make_request("GET", f"sys/policies/rgp/{policy_name}")
                        policy_data = policy_response.json().get("data", {})
                        
                        yield {
                            "name": policy_name,
                            "policy": policy_data.get("policy", ""),
                            "type": "rgp",
                            "namespace": self.vault_client.namespace or "root",
                            "enforcement_level": policy_data.get("enforcement_level"),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get RGP policy {policy_name}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list RGP policies (may require Enterprise): {str(e)}")
        
        # Get EGP policies (Endpoint Governing Policies)
        try:
            egp_policies = self._list_request("sys/policies/egp")
            if egp_policies:
                for policy_name in egp_policies:
                    try:
                        policy_response = self._make_request("GET", f"sys/policies/egp/{policy_name}")
                        policy_data = policy_response.json().get("data", {})
                        
                        yield {
                            "name": policy_name,
                            "policy": policy_data.get("policy", ""),
                            "type": "egp",
                            "namespace": self.vault_client.namespace or "root",
                            "enforcement_level": policy_data.get("enforcement_level"),
                            "paths": policy_data.get("paths", []),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get EGP policy {policy_name}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list EGP policies (may require Enterprise): {str(e)}")
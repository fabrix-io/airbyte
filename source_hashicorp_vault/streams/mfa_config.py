#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class MFAConfigStream(VaultBaseStream):
    """
    Stream for retrieving MFA configuration
    """
    
    @property
    def name(self) -> str:
        return "mfa_config"
    
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
                "type": {"type": "string"},  # "totp", "duo", "okta", "pingid"
                "namespace": {"type": ["string", "null"]},
                "mount_accessor": {"type": ["string", "null"]},
                "config": {"type": ["object", "null"]},
                "enforcement_config": {"type": ["array", "null"], "items": {"type": "object"}},
            },
            "additionalProperties": True,
        }
    
    def _get_identity_mfa(self) -> Iterable[Mapping[str, Any]]:
        """
        Get Identity MFA methods (Enterprise feature)
        """
        try:
            # List MFA methods
            mfa_methods = self._list_request("identity/mfa/method")
            if mfa_methods:
                for method_id in mfa_methods:
                    try:
                        method_response = self._make_request("GET", f"identity/mfa/method/{method_id}")
                        method_data = method_response.json().get("data", {})
                        
                        yield {
                            "id": method_id,
                            "name": method_data.get("name", method_id),
                            "type": method_data.get("type", "unknown"),
                            "namespace": method_data.get("namespace_id", self.vault_client.namespace or "root"),
                            "mount_accessor": method_data.get("mount_accessor"),
                            "config": method_data,
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get MFA method {method_id}: {str(e)}")
                        
            # List MFA login enforcements
            enforcements = self._list_request("identity/mfa/login-enforcement")
            if enforcements:
                for enforcement_name in enforcements:
                    try:
                        enforcement_response = self._make_request("GET", f"identity/mfa/login-enforcement/{enforcement_name}")
                        enforcement_data = enforcement_response.json().get("data", {})
                        
                        yield {
                            "id": f"enforcement-{enforcement_name}",
                            "name": enforcement_name,
                            "type": "enforcement",
                            "namespace": enforcement_data.get("namespace_id", self.vault_client.namespace or "root"),
                            "enforcement_config": [{
                                "mfa_method_ids": enforcement_data.get("mfa_method_ids", []),
                                "auth_method_accessors": enforcement_data.get("auth_method_accessors", []),
                                "auth_method_types": enforcement_data.get("auth_method_types", []),
                                "identity_group_ids": enforcement_data.get("identity_group_ids", []),
                                "identity_entity_ids": enforcement_data.get("identity_entity_ids", []),
                            }],
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get MFA enforcement {enforcement_name}: {str(e)}")
                        
        except Exception as e:
            self.logger.debug(f"Failed to list Identity MFA (may require Enterprise): {str(e)}")
    
    def _get_auth_method_mfa(self) -> Iterable[Mapping[str, Any]]:
        """
        Get MFA configuration from auth methods
        """
        # Check TOTP on userpass
        try:
            # List auth methods
            auth_response = self._make_request("GET", "sys/auth")
            auth_methods = auth_response.json().get("data", {})
            
            for auth_path, auth_info in auth_methods.items():
                if auth_info.get("type") == "userpass":
                    # Check if MFA is configured
                    try:
                        mfa_response = self._make_request("GET", f"auth/{auth_path}mfa_config")
                        mfa_config = mfa_response.json().get("data", {})
                        
                        if mfa_config:
                            yield {
                                "id": f"userpass-{auth_path}-mfa",
                                "name": f"Userpass MFA ({auth_path})",
                                "type": mfa_config.get("type", "totp"),
                                "namespace": self.vault_client.namespace or "root",
                                "mount_accessor": auth_info.get("accessor"),
                                "config": mfa_config,
                            }
                    except Exception as e:
                        self.logger.debug(f"No MFA config for userpass at {auth_path}: {str(e)}")
                        
                elif auth_info.get("type") == "ldap":
                    # Check LDAP MFA config
                    try:
                        # Check for Duo configuration
                        duo_response = self._make_request("GET", f"auth/{auth_path}duo/config")
                        duo_config = duo_response.json().get("data", {})
                        
                        if duo_config and duo_config.get("host"):
                            yield {
                                "id": f"ldap-{auth_path}-duo",
                                "name": f"LDAP Duo MFA ({auth_path})",
                                "type": "duo",
                                "namespace": self.vault_client.namespace or "root",
                                "mount_accessor": auth_info.get("accessor"),
                                "config": {
                                    "host": duo_config.get("host"),
                                    "username_format": duo_config.get("username_format"),
                                    "push_info": duo_config.get("push_info"),
                                },
                            }
                    except Exception as e:
                        self.logger.debug(f"No Duo config for LDAP at {auth_path}: {str(e)}")
                        
        except Exception as e:
            self.logger.warning(f"Failed to check auth method MFA: {str(e)}")
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read MFA configuration from various sources
        """
        # Get Identity-based MFA (Enterprise)
        yield from self._get_identity_mfa()
        
        # Get auth method MFA
        yield from self._get_auth_method_mfa()
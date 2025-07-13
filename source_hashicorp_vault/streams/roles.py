#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, Iterable, Mapping

from .base import VaultBaseStream


class RolesStream(VaultBaseStream):
    """
    Stream for retrieving Vault roles from various auth methods
    """
    
    @property
    def name(self) -> str:
        return "roles"
    
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
                "auth_method": {"type": "string"},
                "policies": {"type": "array", "items": {"type": "string"}},
                "token_policies": {"type": "array", "items": {"type": "string"}},
                "token_ttl": {"type": ["integer", "null"]},
                "token_max_ttl": {"type": ["integer", "null"]},
                "token_period": {"type": ["integer", "null"]},
                "token_bound_cidrs": {"type": "array", "items": {"type": "string"}},
                "role_id": {"type": ["string", "null"]},
                "secret_id_ttl": {"type": ["integer", "null"]},
                "secret_id_num_uses": {"type": ["integer", "null"]},
                "bind_secret_id": {"type": ["boolean", "null"]},
                "bound_cidr_list": {"type": "array", "items": {"type": "string"}},
                "namespace": {"type": ["string", "null"]},
                "metadata": {"type": ["object", "null"]},
            },
            "additionalProperties": True,
        }
    
    def _get_approle_roles(self) -> Iterable[Mapping[str, Any]]:
        """Get roles from AppRole auth method"""
        try:
            roles = self._list_request("auth/approle/role")
            if roles:
                for role_name in roles:
                    try:
                        role_response = self._make_request("GET", f"auth/approle/role/{role_name}")
                        role_data = role_response.json().get("data", {})
                        
                        # Try to get the role ID
                        role_id = None
                        try:
                            role_id_response = self._make_request("GET", f"auth/approle/role/{role_name}/role-id")
                            role_id = role_id_response.json().get("data", {}).get("role_id")
                        except Exception:
                            pass
                        
                        yield {
                            "id": f"approle-{role_name}",
                            "name": role_name,
                            "auth_method": "approle",
                            "policies": role_data.get("policies", []),
                            "token_policies": role_data.get("token_policies", []),
                            "token_ttl": role_data.get("token_ttl"),
                            "token_max_ttl": role_data.get("token_max_ttl"),
                            "token_period": role_data.get("token_period"),
                            "token_bound_cidrs": role_data.get("token_bound_cidrs", []),
                            "role_id": role_id,
                            "secret_id_ttl": role_data.get("secret_id_ttl"),
                            "secret_id_num_uses": role_data.get("secret_id_num_uses"),
                            "bind_secret_id": role_data.get("bind_secret_id"),
                            "bound_cidr_list": role_data.get("bound_cidr_list", []),
                            "namespace": self.vault_client.namespace or "root",
                            "metadata": role_data.get("metadata", {}),
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get AppRole role {role_name}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list AppRole roles: {str(e)}")
    
    def _get_kubernetes_roles(self) -> Iterable[Mapping[str, Any]]:
        """Get roles from Kubernetes auth method"""
        try:
            roles = self._list_request("auth/kubernetes/role")
            if roles:
                for role_name in roles:
                    try:
                        role_response = self._make_request("GET", f"auth/kubernetes/role/{role_name}")
                        role_data = role_response.json().get("data", {})
                        yield {
                            "id": f"kubernetes-{role_name}",
                            "name": role_name,
                            "auth_method": "kubernetes",
                            "policies": role_data.get("policies", []),
                            "token_policies": role_data.get("token_policies", []),
                            "token_ttl": role_data.get("token_ttl"),
                            "token_max_ttl": role_data.get("token_max_ttl"),
                            "token_period": role_data.get("token_period"),
                            "token_bound_cidrs": role_data.get("token_bound_cidrs", []),
                            "namespace": self.vault_client.namespace or "root",
                            "metadata": {
                                "bound_service_account_names": role_data.get("bound_service_account_names", []),
                                "bound_service_account_namespaces": role_data.get("bound_service_account_namespaces", []),
                                "audience": role_data.get("audience"),
                            },
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get Kubernetes role {role_name}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list Kubernetes roles: {str(e)}")
    
    def _get_aws_roles(self) -> Iterable[Mapping[str, Any]]:
        """Get roles from AWS auth method"""
        try:
            roles = self._list_request("auth/aws/role")
            if roles:
                for role_name in roles:
                    try:
                        role_response = self._make_request("GET", f"auth/aws/role/{role_name}")
                        role_data = role_response.json().get("data", {})
                        yield {
                            "id": f"aws-{role_name}",
                            "name": role_name,
                            "auth_method": "aws",
                            "policies": role_data.get("policies", []),
                            "token_policies": role_data.get("token_policies", []),
                            "token_ttl": role_data.get("token_ttl"),
                            "token_max_ttl": role_data.get("token_max_ttl"),
                            "token_period": role_data.get("token_period"),
                            "token_bound_cidrs": role_data.get("token_bound_cidrs", []),
                            "namespace": self.vault_client.namespace or "root",
                            "metadata": {
                                "auth_type": role_data.get("auth_type"),
                                "bound_ami_id": role_data.get("bound_ami_id", []),
                                "bound_account_id": role_data.get("bound_account_id", []),
                                "bound_iam_role_arn": role_data.get("bound_iam_role_arn", []),
                                "bound_iam_instance_profile_arn": role_data.get("bound_iam_instance_profile_arn", []),
                                "bound_ec2_instance_id": role_data.get("bound_ec2_instance_id", []),
                            },
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to get AWS role {role_name}: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Failed to list AWS roles: {str(e)}")
    
    def read_records(
        self,
        sync_mode: str,
        cursor_field: list[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Read roles from various auth methods
        """
        # Get roles from different auth methods
        yield from self._get_approle_roles()
        yield from self._get_kubernetes_roles()
        yield from self._get_aws_roles()
        
        # You can add more auth methods here (LDAP, OIDC, etc.)
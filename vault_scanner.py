#!/usr/bin/env python3
"""
HashiCorp Vault Scanner
Scans Vault for configuration and metadata using AppRole authentication.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Generator
from dataclasses import dataclass, asdict
import requests
from urllib.parse import urljoin
import argparse
import sys


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Configuration for Vault connection"""
    vault_url: str
    role_id: str
    secret_id: str
    namespace: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30


@dataclass
class VaultInfo:
    """Information about the Vault instance"""
    initialized: bool
    sealed: bool
    version: str
    cluster_name: Optional[str] = None
    cluster_id: Optional[str] = None
    ha_enabled: bool = False
    is_self: Optional[bool] = None
    leader_address: Optional[str] = None
    leader_cluster_address: Optional[str] = None
    performance_standby: Optional[bool] = None
    replication_performance_mode: Optional[str] = None
    replication_dr_mode: Optional[str] = None


@dataclass
class User:
    """User information"""
    username: str
    policies: List[str]
    token_policies: List[str]
    metadata: Dict[str, Any]
    namespace: str


@dataclass
class Role:
    """Role information"""
    name: str
    policies: List[str]
    token_policies: List[str]
    namespace: str
    role_type: str  # approle, aws, etc.
    token_ttl: Optional[int] = None
    token_max_ttl: Optional[int] = None


@dataclass
class Policy:
    """Policy information"""
    name: str
    rules: str
    namespace: str


@dataclass
class Group:
    """Group information"""
    id: str
    name: str
    type: str  # internal or external
    policies: List[str]
    member_entity_ids: List[str]
    namespace: str
    metadata: Dict[str, Any]


@dataclass
class Namespace:
    """Namespace information"""
    id: str
    path: str
    custom_metadata: Dict[str, Any]


@dataclass
class Secret:
    """Secret metadata (no values)"""
    path: str
    type: str  # kv, pki, etc.
    namespace: str
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    version: Optional[int] = None


@dataclass
class Permission:
    """Permission mapping"""
    entity_type: str  # user or group
    entity_name: str
    policies: List[str]
    namespace: str
    effective_policies: List[str]  # Including inherited


class VaultScanner:
    """Main scanner class for HashiCorp Vault"""
    
    def __init__(self, config: VaultConfig):
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        self.token = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate using AppRole"""
        logger.info("Authenticating with Vault using AppRole...")
        
        auth_data = {
            "role_id": self.config.role_id,
            "secret_id": self.config.secret_id
        }
        
        headers = {}
        if self.config.namespace:
            headers["X-Vault-Namespace"] = self.config.namespace
        
        try:
            response = self.session.post(
                urljoin(self.config.vault_url, "/v1/auth/approle/login"),
                json=auth_data,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            auth_result = response.json()
            self.token = auth_result["auth"]["client_token"]
            self.session.headers.update({"X-Vault-Token": self.token})
            
            if self.config.namespace:
                self.session.headers.update({"X-Vault-Namespace": self.config.namespace})
            
            logger.info("Successfully authenticated with Vault")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to authenticate with Vault: {e}")
            raise
    
    def _make_request(self, method: str, path: str, namespace: Optional[str] = None, 
                     **kwargs) -> Optional[Dict[str, Any]]:
        """Make an authenticated request to Vault"""
        url = urljoin(self.config.vault_url, path)
        
        headers = kwargs.pop("headers", {})
        if namespace is not None:
            headers["X-Vault-Namespace"] = namespace
        
        try:
            response = self.session.request(
                method,
                url,
                headers=headers,
                timeout=self.config.timeout,
                **kwargs
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {method} {path}: {e}")
            return None
    
    def scan_vault_info(self) -> Optional[VaultInfo]:
        """Scan general Vault information"""
        logger.info("Scanning Vault information...")
        
        # Get health status
        health = self._make_request("GET", "/v1/sys/health")
        if not health:
            return None
        
        # Get leader info
        leader = self._make_request("GET", "/v1/sys/leader")
        
        # Get configuration
        config = self._make_request("GET", "/v1/sys/config/state/sanitized")
        
        # Get replication status if available
        repl_perf = self._make_request("GET", "/v1/sys/replication/performance/status")
        repl_dr = self._make_request("GET", "/v1/sys/replication/dr/status")
        
        return VaultInfo(
            initialized=health.get("initialized", False),
            sealed=health.get("sealed", False),
            version=health.get("version", "unknown"),
            cluster_name=health.get("cluster_name"),
            cluster_id=health.get("cluster_id"),
            ha_enabled=leader.get("ha_enabled", False) if leader else False,
            is_self=leader.get("is_self") if leader else None,
            leader_address=leader.get("leader_address") if leader else None,
            leader_cluster_address=leader.get("leader_cluster_address") if leader else None,
            performance_standby=health.get("performance_standby"),
            replication_performance_mode=repl_perf.get("mode") if repl_perf else None,
            replication_dr_mode=repl_dr.get("mode") if repl_dr else None
        )
    
    def scan_users(self, namespace: Optional[str] = None) -> Generator[User, None, None]:
        """Scan users in the given namespace"""
        ns = namespace or self.config.namespace or ""
        logger.info(f"Scanning users in namespace: {ns or 'root'}")
        
        # List users (assuming userpass auth method)
        users_list = self._make_request("LIST", "/v1/auth/userpass/users", namespace=ns)
        
        if not users_list or "data" not in users_list:
            logger.warning(f"No users found in namespace: {ns or 'root'}")
            return
        
        for username in users_list["data"].get("keys", []):
            user_data = self._make_request("GET", f"/v1/auth/userpass/users/{username}", namespace=ns)
            
            if user_data and "data" in user_data:
                data = user_data["data"]
                yield User(
                    username=username,
                    policies=data.get("policies", []),
                    token_policies=data.get("token_policies", []),
                    metadata=data.get("metadata", {}),
                    namespace=ns
                )
    
    def scan_roles(self, namespace: Optional[str] = None) -> Generator[Role, None, None]:
        """Scan roles in the given namespace"""
        ns = namespace or self.config.namespace or ""
        logger.info(f"Scanning roles in namespace: {ns or 'root'}")
        
        # Scan AppRole roles
        approle_list = self._make_request("LIST", "/v1/auth/approle/role", namespace=ns)
        
        if approle_list and "data" in approle_list:
            for role_name in approle_list["data"].get("keys", []):
                role_data = self._make_request("GET", f"/v1/auth/approle/role/{role_name}", namespace=ns)
                
                if role_data and "data" in role_data:
                    data = role_data["data"]
                    yield Role(
                        name=role_name,
                        policies=data.get("policies", []),
                        token_policies=data.get("token_policies", []),
                        token_ttl=data.get("token_ttl"),
                        token_max_ttl=data.get("token_max_ttl"),
                        namespace=ns,
                        role_type="approle"
                    )
    
    def scan_policies(self, namespace: Optional[str] = None) -> Generator[Policy, None, None]:
        """Scan policies in the given namespace"""
        ns = namespace or self.config.namespace or ""
        logger.info(f"Scanning policies in namespace: {ns or 'root'}")
        
        # List policies
        policies_list = self._make_request("LIST", "/v1/sys/policies/acl", namespace=ns)
        
        if not policies_list or "data" not in policies_list:
            logger.warning(f"No policies found in namespace: {ns or 'root'}")
            return
        
        for policy_name in policies_list["data"].get("keys", []):
            policy_data = self._make_request("GET", f"/v1/sys/policies/acl/{policy_name}", namespace=ns)
            
            if policy_data and "data" in policy_data:
                yield Policy(
                    name=policy_name,
                    rules=policy_data["data"].get("policy", ""),
                    namespace=ns
                )
    
    def scan_groups(self, namespace: Optional[str] = None) -> Generator[Group, None, None]:
        """Scan groups in the given namespace"""
        ns = namespace or self.config.namespace or ""
        logger.info(f"Scanning groups in namespace: {ns or 'root'}")
        
        # List groups
        groups_list = self._make_request("LIST", "/v1/identity/group", namespace=ns)
        
        if not groups_list or "data" not in groups_list:
            logger.warning(f"No groups found in namespace: {ns or 'root'}")
            return
        
        for group_id in groups_list["data"].get("keys", []):
            group_data = self._make_request("GET", f"/v1/identity/group/id/{group_id}", namespace=ns)
            
            if group_data and "data" in group_data:
                data = group_data["data"]
                yield Group(
                    id=group_id,
                    name=data.get("name", ""),
                    type=data.get("type", "internal"),
                    policies=data.get("policies", []),
                    member_entity_ids=data.get("member_entity_ids", []),
                    namespace=ns,
                    metadata=data.get("metadata", {})
                )
    
    def scan_namespaces(self, parent_ns: Optional[str] = None) -> Generator[Namespace, None, None]:
        """Recursively scan namespaces"""
        ns = parent_ns or self.config.namespace or ""
        logger.info(f"Scanning namespaces under: {ns or 'root'}")
        
        # List namespaces
        ns_list = self._make_request("LIST", "/v1/sys/namespaces", namespace=ns)
        
        if not ns_list or "data" not in ns_list:
            return
        
        for ns_name in ns_list["data"].get("keys", []):
            ns_data = self._make_request("GET", f"/v1/sys/namespaces/{ns_name}", namespace=ns)
            
            if ns_data and "data" in ns_data:
                data = ns_data["data"]
                namespace_obj = Namespace(
                    id=data.get("id", ""),
                    path=data.get("path", ns_name),
                    custom_metadata=data.get("custom_metadata", {})
                )
                yield namespace_obj
                
                # Recursively scan child namespaces
                child_ns = f"{ns}/{ns_name}".strip("/") if ns else ns_name
                yield from self.scan_namespaces(child_ns)
    
    def scan_secrets(self, namespace: Optional[str] = None, mount_path: str = "secret") -> Generator[Secret, None, None]:
        """Recursively scan secrets metadata"""
        ns = namespace or self.config.namespace or ""
        logger.info(f"Scanning secrets in namespace: {ns or 'root'}, mount: {mount_path}")
        
        def scan_path(path: str = ""):
            """Recursively scan a path"""
            list_path = f"/v1/{mount_path}/metadata/{path}" if path else f"/v1/{mount_path}/metadata"
            
            result = self._make_request("LIST", list_path, namespace=ns)
            
            if not result or "data" not in result:
                return
            
            for key in result["data"].get("keys", []):
                full_path = f"{path}{key}" if path else key
                
                if key.endswith("/"):
                    # It's a directory, recurse
                    yield from scan_path(full_path)
                else:
                    # It's a secret, get metadata
                    metadata_path = f"/v1/{mount_path}/metadata/{full_path}"
                    metadata = self._make_request("GET", metadata_path, namespace=ns)
                    
                    if metadata and "data" in metadata:
                        data = metadata["data"]
                        yield Secret(
                            path=full_path,
                            type="kv-v2",
                            namespace=ns,
                            created_time=data.get("created_time"),
                            updated_time=data.get("updated_time"),
                            version=data.get("current_version")
                        )
        
        yield from scan_path()
    
    def scan_permissions(self, namespace: Optional[str] = None) -> Generator[Permission, None, None]:
        """Scan permissions for users and groups"""
        ns = namespace or self.config.namespace or ""
        logger.info(f"Scanning permissions in namespace: {ns or 'root'}")
        
        # Get all policies first
        all_policies = {p.name: p for p in self.scan_policies(ns)}
        
        # Scan user permissions
        for user in self.scan_users(ns):
            effective_policies = []
            # Combine token_policies and policies
            for policy_name in set(user.policies + user.token_policies):
                if policy_name in all_policies:
                    effective_policies.append(policy_name)
            
            yield Permission(
                entity_type="user",
                entity_name=user.username,
                policies=user.policies,
                namespace=ns,
                effective_policies=effective_policies
            )
        
        # Scan group permissions
        for group in self.scan_groups(ns):
            yield Permission(
                entity_type="group",
                entity_name=group.name,
                policies=group.policies,
                namespace=ns,
                effective_policies=group.policies  # Groups don't have token policies
            )
    
    def scan_all(self, output_format: str = "json") -> Dict[str, List[Dict[str, Any]]]:
        """Perform a complete scan of all resources"""
        logger.info("Starting complete Vault scan...")
        
        results = {
            "vault_info": None,
            "users": [],
            "roles": [],
            "policies": [],
            "groups": [],
            "namespaces": [],
            "secrets": [],
            "permissions": []
        }
        
        # Scan vault info
        vault_info = self.scan_vault_info()
        if vault_info:
            results["vault_info"] = asdict(vault_info)
        
        # Get current namespace for scanning
        current_ns = self.config.namespace or ""
        
        # Scan all resources in current namespace
        results["users"] = [asdict(u) for u in self.scan_users(current_ns)]
        results["roles"] = [asdict(r) for r in self.scan_roles(current_ns)]
        results["policies"] = [asdict(p) for p in self.scan_policies(current_ns)]
        results["groups"] = [asdict(g) for g in self.scan_groups(current_ns)]
        results["permissions"] = [asdict(p) for p in self.scan_permissions(current_ns)]
        
        # Scan namespaces recursively
        all_namespaces = list(self.scan_namespaces(current_ns))
        results["namespaces"] = [asdict(ns) for ns in all_namespaces]
        
        # Scan secrets in current namespace
        results["secrets"] = [asdict(s) for s in self.scan_secrets(current_ns)]
        
        # Optionally scan resources in child namespaces
        for ns in all_namespaces:
            ns_path = ns.path
            if current_ns:
                full_ns = f"{current_ns}/{ns_path}".strip("/")
            else:
                full_ns = ns_path
            
            # Scan resources in child namespace
            for user in self.scan_users(full_ns):
                results["users"].append(asdict(user))
            
            for role in self.scan_roles(full_ns):
                results["roles"].append(asdict(role))
            
            for policy in self.scan_policies(full_ns):
                results["policies"].append(asdict(policy))
            
            for group in self.scan_groups(full_ns):
                results["groups"].append(asdict(group))
            
            for perm in self.scan_permissions(full_ns):
                results["permissions"].append(asdict(perm))
            
            for secret in self.scan_secrets(full_ns):
                results["secrets"].append(asdict(secret))
        
        logger.info("Vault scan completed")
        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="HashiCorp Vault Scanner")
    parser.add_argument("--vault-url", required=True, help="Vault server URL")
    parser.add_argument("--role-id", required=True, help="AppRole role ID")
    parser.add_argument("--secret-id", required=True, help="AppRole secret ID")
    parser.add_argument("--namespace", help="Starting namespace (default: root for self-hosted, admin for HCP)")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification")
    parser.add_argument("--output", default="scan_results.json", help="Output file (default: scan_results.json)")
    parser.add_argument("--format", choices=["json", "summary"], default="json", help="Output format")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    
    args = parser.parse_args()
    
    # Auto-detect namespace if not provided
    if args.namespace is None:
        if "hashicorp.cloud" in args.vault_url:
            args.namespace = "admin"
            logger.info("Detected HCP Vault, using 'admin' namespace")
        else:
            args.namespace = ""
            logger.info("Using root namespace for self-hosted Vault")
    
    # Create configuration
    config = VaultConfig(
        vault_url=args.vault_url.rstrip("/"),
        role_id=args.role_id,
        secret_id=args.secret_id,
        namespace=args.namespace,
        verify_ssl=not args.no_verify_ssl,
        timeout=args.timeout
    )
    
    try:
        # Initialize scanner
        scanner = VaultScanner(config)
        
        # Perform scan
        results = scanner.scan_all(output_format=args.format)
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Scan results saved to {args.output}")
        
        # Print summary if requested
        if args.format == "summary":
            print("\n=== Vault Scan Summary ===")
            print(f"Vault Version: {results['vault_info']['version'] if results['vault_info'] else 'Unknown'}")
            print(f"Users: {len(results['users'])}")
            print(f"Roles: {len(results['roles'])}")
            print(f"Policies: {len(results['policies'])}")
            print(f"Groups: {len(results['groups'])}")
            print(f"Namespaces: {len(results['namespaces'])}")
            print(f"Secrets: {len(results['secrets'])}")
            print(f"Permissions: {len(results['permissions'])}")
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
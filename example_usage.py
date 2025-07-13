#!/usr/bin/env python3
"""
Example usage of the Vault Scanner programmatically
"""

from vault_scanner import VaultConfig, VaultScanner
import json

def main():
    # Configure the scanner
    config = VaultConfig(
        vault_url="https://vault-cluster-public-vault-f1897343.66cde020.z1.hashicorp.cloud:8200",
        role_id="your-role-id",
        secret_id="your-secret-id",
        namespace="admin",  # For HCP Vault
        verify_ssl=True,
        timeout=30
    )
    
    # Initialize scanner
    scanner = VaultScanner(config)
    
    # Example 1: Get Vault information
    print("=== Vault Information ===")
    vault_info = scanner.scan_vault_info()
    if vault_info:
        print(f"Version: {vault_info.version}")
        print(f"Sealed: {vault_info.sealed}")
        print(f"HA Enabled: {vault_info.ha_enabled}")
    
    # Example 2: List all users
    print("\n=== Users ===")
    for user in scanner.scan_users():
        print(f"User: {user.username}")
        print(f"  Policies: {', '.join(user.policies)}")
        print(f"  Namespace: {user.namespace}")
    
    # Example 3: List all policies
    print("\n=== Policies ===")
    for policy in scanner.scan_policies():
        print(f"Policy: {policy.name} (namespace: {policy.namespace})")
    
    # Example 4: List namespaces recursively
    print("\n=== Namespaces ===")
    for namespace in scanner.scan_namespaces():
        print(f"Namespace: {namespace.path} (ID: {namespace.id})")
    
    # Example 5: List secrets (metadata only)
    print("\n=== Secrets ===")
    for secret in scanner.scan_secrets():
        print(f"Secret: {secret.path}")
        print(f"  Type: {secret.type}")
        print(f"  Version: {secret.version}")
        print(f"  Updated: {secret.updated_time}")
    
    # Example 6: Get permissions mapping
    print("\n=== Permissions ===")
    for perm in scanner.scan_permissions():
        print(f"{perm.entity_type.capitalize()}: {perm.entity_name}")
        print(f"  Direct Policies: {', '.join(perm.policies)}")
        print(f"  Effective Policies: {', '.join(perm.effective_policies)}")
    
    # Example 7: Complete scan
    print("\n=== Running Complete Scan ===")
    results = scanner.scan_all()
    
    # Save to file
    with open("scan_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nComplete scan results saved to scan_results.json")
    print(f"Found {len(results['users'])} users")
    print(f"Found {len(results['policies'])} policies")
    print(f"Found {len(results['secrets'])} secrets")

if __name__ == "__main__":
    main()
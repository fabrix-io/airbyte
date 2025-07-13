#!/usr/bin/env python3
"""
Quick start guide for Vault Scanner

This example shows how to use the scanner with the values from setup-fabrix-read.sh
"""

import sys
import json
from vault_scanner import VaultConfig, VaultScanner

# Example values from setup-fabrix-read.sh
EXAMPLE_CONFIG = {
    "vault_url": "https://vault-cluster-public-vault-f1897343.66cde020.z1.hashicorp.cloud:8200",
    "role_id": "59a3055e-b987-7d87-e422-ba53239a7f0e",
    "secret_id": "c92937b5-b525-872d-beb1-44a94db2ba3a",
    "namespace": "admin"  # For HCP Vault
}

def main():
    print("=== Vault Scanner Quick Start ===\n")
    
    # You can override these with command line arguments
    vault_url = sys.argv[1] if len(sys.argv) > 1 else EXAMPLE_CONFIG["vault_url"]
    role_id = sys.argv[2] if len(sys.argv) > 2 else EXAMPLE_CONFIG["role_id"]
    secret_id = sys.argv[3] if len(sys.argv) > 3 else EXAMPLE_CONFIG["secret_id"]
    namespace = sys.argv[4] if len(sys.argv) > 4 else EXAMPLE_CONFIG["namespace"]
    
    print(f"Using configuration:")
    print(f"  Vault URL: {vault_url}")
    print(f"  Role ID: {role_id[:8]}...")
    print(f"  Secret ID: {secret_id[:8]}...")
    print(f"  Namespace: {namespace}")
    print()
    
    # Create configuration
    config = VaultConfig(
        vault_url=vault_url,
        role_id=role_id,
        secret_id=secret_id,
        namespace=namespace,
        verify_ssl=True
    )
    
    try:
        # Initialize scanner
        print("Initializing scanner...")
        scanner = VaultScanner(config)
        print("Successfully authenticated!\n")
        
        # Get vault info
        vault_info = scanner.scan_vault_info()
        if vault_info:
            print(f"Vault Version: {vault_info.version}")
            print(f"Initialized: {vault_info.initialized}")
            print(f"Sealed: {vault_info.sealed}")
            print()
        
        # Quick scan of available resources
        print("Scanning resources...")
        
        # Count resources
        users = list(scanner.scan_users())
        print(f"Found {len(users)} users")
        
        policies = list(scanner.scan_policies())
        print(f"Found {len(policies)} policies")
        if policies:
            print(f"  Sample policies: {', '.join(p.name for p in policies[:3])}")
        
        namespaces = list(scanner.scan_namespaces())
        print(f"Found {len(namespaces)} namespaces")
        
        # Perform complete scan
        print("\nPerforming complete scan...")
        results = scanner.scan_all()
        
        # Save results
        output_file = "quick_scan_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to {output_file}")
        
        # Print summary
        print("\n=== Scan Summary ===")
        for key, value in results.items():
            if isinstance(value, list):
                print(f"{key}: {len(value)} items")
            elif value:
                print(f"{key}: Available")
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nUsage: python quick_start.py [vault_url] [role_id] [secret_id] [namespace]")
        sys.exit(1)

if __name__ == "__main__":
    main()
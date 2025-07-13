#!/usr/bin/env python3
"""
Test script for the HashiCorp Vault Airbyte connector.

Usage:
    python test_connector.py

Make sure to create a config.json file with your Vault credentials first.
"""

import json
import subprocess
import sys


def run_command(command):
    """Run a command and return the output."""
    print(f"\nRunning: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    
    return result.stdout


def main():
    """Test the connector with various commands."""
    
    # Check if config.json exists
    try:
        with open("secrets/config.json", "r") as f:
            config = json.load(f)
        print("✓ Found config.json")
    except FileNotFoundError:
        print("✗ Error: Please create secrets/config.json with your Vault credentials")
        print("  You can use secrets/config.json.example as a template")
        sys.exit(1)
    
    # Test 1: Check connection
    print("\n1. Testing connection...")
    output = run_command(["python", "main.py", "check", "--config", "secrets/config.json"])
    result = json.loads(output)
    
    if result.get("status") == "SUCCEEDED":
        print("✓ Connection successful!")
    else:
        print(f"✗ Connection failed: {result.get('message')}")
        sys.exit(1)
    
    # Test 2: Discover schema
    print("\n2. Discovering schema...")
    output = run_command(["python", "main.py", "discover", "--config", "secrets/config.json"])
    catalog = json.loads(output)
    
    print(f"✓ Found {len(catalog['catalog']['streams'])} streams:")
    for stream in catalog['catalog']['streams']:
        print(f"  - {stream['name']}")
    
    # Test 3: Read some data (just vault stream for quick test)
    print("\n3. Reading vault information...")
    
    # Create a configured catalog for just the vault stream
    configured_catalog = {
        "streams": [
            {
                "stream": stream,
                "sync_mode": "full_refresh",
                "destination_sync_mode": "overwrite"
            }
            for stream in catalog['catalog']['streams']
            if stream['name'] == 'vault'
        ]
    }
    
    with open("configured_catalog.json", "w") as f:
        json.dump(configured_catalog, f)
    
    output = run_command([
        "python", "main.py", "read",
        "--config", "secrets/config.json",
        "--catalog", "configured_catalog.json"
    ])
    
    # Parse and display the vault information
    for line in output.strip().split('\n'):
        try:
            record = json.loads(line)
            if record['type'] == 'RECORD' and record['record']['stream'] == 'vault':
                vault_data = record['record']['data']
                print("\n✓ Vault Information:")
                print(f"  - Cluster ID: {vault_data.get('cluster_id', 'N/A')}")
                print(f"  - Version: {vault_data.get('version', 'N/A')}")
                print(f"  - Namespace: {vault_data.get('namespace', 'N/A')}")
                print(f"  - Self-hosted: {vault_data.get('is_self_hosted', 'N/A')}")
                print(f"  - HA Enabled: {vault_data.get('high_availability_enabled', 'N/A')}")
        except json.JSONDecodeError:
            pass
    
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    main()
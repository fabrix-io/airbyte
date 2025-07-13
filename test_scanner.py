#!/usr/bin/env python3
"""
Test script for Vault Scanner
Tests basic functionality without requiring actual Vault connection
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from vault_scanner import (
    VaultConfig, VaultScanner, VaultInfo, User, Role, 
    Policy, Group, Namespace, Secret, Permission
)


class TestVaultScanner(unittest.TestCase):
    
    def setUp(self):
        """Set up test configuration"""
        self.config = VaultConfig(
            vault_url="https://vault.example.com:8200",
            role_id="test-role-id",
            secret_id="test-secret-id",
            namespace="admin"
        )
    
    @patch('vault_scanner.requests.Session')
    def test_authentication(self, mock_session):
        """Test AppRole authentication"""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "auth": {
                "client_token": "test-token"
            }
        }
        mock_response.raise_for_status = Mock()
        
        # Mock session
        mock_session_instance = Mock()
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Test authentication
        scanner = VaultScanner(self.config)
        
        # Verify authentication was called
        mock_session_instance.post.assert_called_once()
        self.assertEqual(scanner.token, "test-token")
    
    @patch('vault_scanner.VaultScanner._authenticate')
    @patch('vault_scanner.VaultScanner._make_request')
    def test_scan_vault_info(self, mock_request, mock_auth):
        """Test scanning vault information"""
        # Mock responses
        mock_request.side_effect = [
            # Health response
            {
                "initialized": True,
                "sealed": False,
                "version": "1.15.0",
                "cluster_name": "test-cluster",
                "cluster_id": "123"
            },
            # Leader response
            {
                "ha_enabled": True,
                "is_self": True,
                "leader_address": "https://vault.example.com:8200"
            },
            # Config response
            None,
            # Replication responses
            None,
            None
        ]
        
        scanner = VaultScanner(self.config)
        vault_info = scanner.scan_vault_info()
        
        self.assertIsInstance(vault_info, VaultInfo)
        self.assertTrue(vault_info.initialized)
        self.assertFalse(vault_info.sealed)
        self.assertEqual(vault_info.version, "1.15.0")
        self.assertTrue(vault_info.ha_enabled)
    
    @patch('vault_scanner.VaultScanner._authenticate')
    @patch('vault_scanner.VaultScanner._make_request')
    def test_scan_users(self, mock_request, mock_auth):
        """Test scanning users"""
        # Mock responses
        mock_request.side_effect = [
            # List users
            {
                "data": {
                    "keys": ["user1", "user2"]
                }
            },
            # Get user1
            {
                "data": {
                    "policies": ["default", "read-only"],
                    "token_policies": ["default"],
                    "metadata": {"created": "2023-01-01"}
                }
            },
            # Get user2
            {
                "data": {
                    "policies": ["admin"],
                    "token_policies": ["admin"],
                    "metadata": {}
                }
            }
        ]
        
        scanner = VaultScanner(self.config)
        users = list(scanner.scan_users())
        
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].username, "user1")
        self.assertEqual(users[0].policies, ["default", "read-only"])
        self.assertEqual(users[1].username, "user2")
        self.assertEqual(users[1].policies, ["admin"])
    
    @patch('vault_scanner.VaultScanner._authenticate')
    @patch('vault_scanner.VaultScanner._make_request')
    def test_scan_policies(self, mock_request, mock_auth):
        """Test scanning policies"""
        # Mock responses
        mock_request.side_effect = [
            # List policies
            {
                "data": {
                    "keys": ["default", "admin", "read-only"]
                }
            },
            # Get default policy
            {
                "data": {
                    "policy": "path \"secret/*\" {\n  capabilities = [\"read\"]\n}"
                }
            },
            # Get admin policy
            {
                "data": {
                    "policy": "path \"*\" {\n  capabilities = [\"create\", \"read\", \"update\", \"delete\", \"list\", \"sudo\"]\n}"
                }
            },
            # Get read-only policy
            {
                "data": {
                    "policy": "path \"secret/data/*\" {\n  capabilities = [\"read\"]\n}"
                }
            }
        ]
        
        scanner = VaultScanner(self.config)
        policies = list(scanner.scan_policies())
        
        self.assertEqual(len(policies), 3)
        self.assertEqual(policies[0].name, "default")
        self.assertIn("capabilities", policies[0].rules)
    
    @patch('vault_scanner.VaultScanner._authenticate')
    @patch('vault_scanner.VaultScanner._make_request')
    def test_scan_namespaces_recursive(self, mock_request, mock_auth):
        """Test recursive namespace scanning"""
        # Mock responses
        mock_request.side_effect = [
            # List root namespaces
            {
                "data": {
                    "keys": ["ns1/", "ns2/"]
                }
            },
            # Get ns1
            {
                "data": {
                    "id": "ns1-id",
                    "path": "ns1/",
                    "custom_metadata": {}
                }
            },
            # List ns1 children (empty)
            None,
            # Get ns2
            {
                "data": {
                    "id": "ns2-id",
                    "path": "ns2/",
                    "custom_metadata": {"owner": "team2"}
                }
            },
            # List ns2 children
            {
                "data": {
                    "keys": ["child/"]
                }
            },
            # Get ns2/child
            {
                "data": {
                    "id": "child-id",
                    "path": "ns2/child/",
                    "custom_metadata": {}
                }
            },
            # List ns2/child children (empty)
            None
        ]
        
        scanner = VaultScanner(self.config)
        namespaces = list(scanner.scan_namespaces())
        
        self.assertEqual(len(namespaces), 3)
        paths = [ns.path for ns in namespaces]
        self.assertIn("ns1/", paths)
        self.assertIn("ns2/", paths)
        self.assertIn("ns2/child/", paths)
    
    def test_vault_config(self):
        """Test VaultConfig dataclass"""
        config = VaultConfig(
            vault_url="https://vault.example.com",
            role_id="role123",
            secret_id="secret456",
            namespace="admin"
        )
        
        self.assertEqual(config.vault_url, "https://vault.example.com")
        self.assertEqual(config.role_id, "role123")
        self.assertEqual(config.secret_id, "secret456")
        self.assertEqual(config.namespace, "admin")
        self.assertTrue(config.verify_ssl)
        self.assertEqual(config.timeout, 30)


if __name__ == "__main__":
    unittest.main()
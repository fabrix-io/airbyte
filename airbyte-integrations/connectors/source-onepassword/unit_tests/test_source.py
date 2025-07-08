#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

import pytest
from unittest.mock import MagicMock, patch
from source_onepassword.source import SourceOnepassword


def test_check_connection_success():
    """Test successful connection check"""
    source = SourceOnepassword()
    logger_mock = MagicMock()
    config = {"access_token": "test-token"}
    
    with patch('subprocess.run') as mock_run:
        # Mock successful 1Password CLI response
        mock_run.return_value = MagicMock(
            stdout='{"id": "test-account", "name": "Test Account"}',
            stderr='',
            returncode=0
        )
        
        result, error = source.check_connection(logger_mock, config)
        
        assert result is True
        assert error is None
        
        # Verify the CLI was called with correct parameters
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["op", "account", "get", "--format=json"]


def test_check_connection_failure():
    """Test failed connection check"""
    source = SourceOnepassword()
    logger_mock = MagicMock()
    config = {"access_token": "invalid-token"}
    
    with patch('subprocess.run') as mock_run:
        # Mock failed 1Password CLI response
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["op", "account", "get"],
            stderr="Authentication failed"
        )
        
        result, error = source.check_connection(logger_mock, config)
        
        assert result is False
        assert "Failed to connect to 1Password" in error


def test_check_connection_no_cli():
    """Test connection check when CLI is not installed"""
    source = SourceOnepassword()
    logger_mock = MagicMock()
    config = {"access_token": "test-token"}
    
    with patch('subprocess.run') as mock_run:
        # Mock FileNotFoundError when CLI is not found
        mock_run.side_effect = FileNotFoundError()
        
        result, error = source.check_connection(logger_mock, config)
        
        assert result is False
        assert "1Password CLI (op) is not installed" in error


def test_streams():
    """Test that all expected streams are returned"""
    source = SourceOnepassword()
    config = {"access_token": "test-token"}
    
    streams = source.streams(config)
    
    # Check that we have the expected number of streams
    assert len(streams) == 7
    
    # Check stream names
    stream_names = [stream.name for stream in streams]
    expected_streams = [
        "account",
        "vaults",
        "groups",
        "service_accounts",
        "users",
        "items",
        "group_memberships"
    ]
    
    for expected_stream in expected_streams:
        assert expected_stream in stream_names


# Add subprocess import for the tests
import subprocess
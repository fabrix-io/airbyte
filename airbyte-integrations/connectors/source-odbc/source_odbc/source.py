import os
import sys
import tempfile
import textwrap
from binascii import unhexlify
from typing import Any, List, Mapping, Optional, Tuple

import pyodbc
from airbyte_cdk import AbstractSource
from airbyte_cdk.sources.streams import Stream
from impacket.krb5 import constants
from impacket.krb5.ccache import CCache
from impacket.krb5.kerberosv5 import getKerberosTGT
from impacket.krb5.types import Principal

from .streams import (
    DatabaseMetadataStream,
    SchemasStream,
    TablesStream,
    ColumnsStream,
    IndexesStream,
    ForeignKeysStream,
    AllTableDataStream,
)



class SourceOdbc(AbstractSource):
    def __init__(self):
        super().__init__()
        self._temp_files = []  # Track temporary files for cleanup

    def check_connection(self, logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[str]]:
        try:
            conn = self._get_odbc_connection(config)
            # Simple test query to verify connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True, None

        except Exception as e:
            return False, f"Error connecting to ODBC server: {str(e)}"
        finally:
            # Cleanup temporary files
            self._cleanup_temp_files()

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """Return all available streams."""
        
        streams = [
            DatabaseMetadataStream(config=config),
            SchemasStream(config=config),
            TablesStream(config=config),
            ColumnsStream(config=config),
            IndexesStream(config=config),
            ForeignKeysStream(config=config),
            AllTableDataStream(config=config)
        ]
        
        return streams

    def _cleanup_temp_files(self):
        """Clean up temporary Kerberos files."""
        for file_path in self._temp_files:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception:
                    pass  # Ignore cleanup errors
        self._temp_files.clear()

    def _setup_kerberos_config(self, realm: str, kdc_host: str) -> Tuple[str, str]:
        """Setup Kerberos configuration."""
        krb5_conf = textwrap.dedent(f"""
        [libdefaults]
          default_realm = {realm}
          dns_lookup_kdc = false
          dns_lookup_realm = false
          rdns = false
          ticket_lifetime = 24h
          forwardable = true
          udp_preference_limit = 1

        [realms]
          {realm} = {{
            kdc = {kdc_host}
            admin_server = {kdc_host}
          }}

        [domain_realm]
          .compute-1.amazonaws.com = {realm}
          compute-1.amazonaws.com = {realm}
          .{realm.lower()} = {realm}
          {realm.lower()} = {realm}
        """).strip() + "\n"
        
        krb5_path = tempfile.mktemp(prefix="krb5_", suffix=".conf")
        with open(krb5_path, "w") as f:
            f.write(krb5_conf)
        os.environ["KRB5_CONFIG"] = krb5_path
        self._temp_files.append(krb5_path)
        
        # Set up credential cache
        ccache_path = tempfile.mktemp(prefix="krbcc_", suffix=".ccache")
        os.environ["KRB5CCNAME"] = f"FILE:{ccache_path}"
        os.environ["KRB5_CCNAME"] = f"FILE:{ccache_path}"
        self._temp_files.append(ccache_path)
        
        return krb5_path, ccache_path

    def _authenticate_with_kerberos(self, username: str, password: str, realm: str, kdc_host: str) -> str:
        """Use impacket for pure Python Kerberos authentication."""
        client = Principal(username, type=constants.PrincipalNameType.NT_PRINCIPAL.value)
        
        tgt, cipher, old_session_key, session_key = getKerberosTGT(
            clientName=client,
            password=password,
            domain=realm,
            lmhash=unhexlify(b""),
            nthash=unhexlify(b""),
            aesKey=None,
            kdcHost=kdc_host
        )

        # Save to ccache file
        ccache_path = os.environ.get("KRB5CCNAME", "").replace("FILE:", "")
        if not ccache_path:
            ccache_path = tempfile.mktemp(prefix="impacket_", suffix=".ccache")
            os.environ["KRB5CCNAME"] = f"FILE:{ccache_path}"
            os.environ["KRB5_CCNAME"] = f"FILE:{ccache_path}"
            self._temp_files.append(ccache_path)
        
        # Create and save ccache
        cc = CCache()
        cc.fromTGT(tgt, old_session_key, session_key)
        cc.saveFile(ccache_path)
        
        # Set proper permissions (important for security)
        os.chmod(ccache_path, 0o600)
        
        return ccache_path

    def _get_odbc_connection(self, config: Mapping[str, Any]) -> Any:
        """Create an ODBC connection with Active Directory authentication."""
        
        # Extract configuration parameters
        dsn = config.get('dsn', '')
        server = config['server']
        database = config['database']
        username = config['username']
        password = config['password']
        port = config.get('port', 1433)
        driver = config.get('driver', 'ODBC Driver 18 for SQL Server')
        auth_type = config.get('authentication_type', 'ActiveDirectory')
        encrypt = config.get('encrypt', True)
        trust_cert = config.get('trust_server_certificate', False)
        timeout = config.get('connection_timeout', 30)
        
        # Kerberos-specific parameters
        realm = config.get('realm')
        kdc_host = config.get('kdc_host')

        # Setup Kerberos authentication if required
        if auth_type == "ActiveDirectoryKerberos":
            if not realm or not kdc_host:
                raise ValueError("realm and kdc_host are required for ActiveDirectoryKerberos authentication")
            
            # Setup Kerberos configuration and authenticate
            krb5_path, ccache_path = self._setup_kerberos_config(realm, kdc_host)
            actual_ccache = self._authenticate_with_kerberos(username, password, realm, kdc_host)

        # Find available SQL Server driver
        if auth_type in ["ActiveDirectoryKerberos", "ActiveDirectoryIntegrated"] and not driver:
            available_drivers = pyodbc.drivers()
            driver = next((d for d in ("ODBC Driver 18 for SQL Server",
                                     "ODBC Driver 17 for SQL Server", 
                                     "SQL Server") if d in available_drivers), None)
            if not driver:
                raise ValueError(f"No SQL Server ODBC driver found. Available: {list(available_drivers)}")

        # Build connection string
        if dsn and not dsn.startswith('DRIVER='):
            # Using a pre-configured DSN
            conn_str = f"DSN={dsn};UID={username};PWD={password}"
        else:
            # Build full connection string
            conn_str_parts = []
            
            if dsn and dsn.startswith('DRIVER='):
                # Use provided connection string as base
                conn_str_parts.append(dsn)
            else:
                # Build from individual components
                conn_str_parts.extend([
                    f"DRIVER={{{driver}}}",
                    f"SERVER={server},{port}" if port != 1433 else f"SERVER={server}",
                    f"DATABASE={database}",
                ])
            
            # Add authentication based on type
            if auth_type == "ActiveDirectory":
                conn_str_parts.extend([
                    f"UID={username}",
                    f"PWD={password}",
                    "Authentication=ActiveDirectoryPassword"
                ])
            elif auth_type == "ActiveDirectoryIntegrated" or auth_type == "ActiveDirectoryKerberos":
                # For Kerberos, we use Trusted_Connection which relies on the Kerberos ticket
                conn_str_parts.append("Trusted_Connection=Yes")
            elif auth_type == "ActiveDirectoryPassword":
                conn_str_parts.extend([
                    f"UID={username}",
                    f"PWD={password}",
                    "Authentication=ActiveDirectoryPassword"
                ])
            else:  # SqlServerAuthentication
                conn_str_parts.extend([
                    f"UID={username}",
                    f"PWD={password}"
                ])
            
            # Add security settings
            if encrypt:
                conn_str_parts.append("Encrypt=yes")
            
            if trust_cert:
                conn_str_parts.append("TrustServerCertificate=yes")
            
            conn_str = ';'.join(conn_str_parts)

        # Create connection
        connection = pyodbc.connect(
            conn_str,
            timeout=timeout,
            autocommit=True
        )
        
        return connection

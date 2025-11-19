"""
Trino Resource for Dagster

Provides a reusable resource for querying Trino (Iceberg catalog)
from Dagster assets. Used for data quality monitoring and analytics.

Usage:
    @asset
    def my_asset(trino_resource):
        results = trino_resource.execute_query("SELECT * FROM my_table")
"""

from dagster import ConfigurableResource
from typing import List, Dict, Any
from pydantic import Field
import subprocess
import json


class TrinoResource(ConfigurableResource):
    """
    Trino query resource for Dagster assets.

    Executes SQL queries against Trino using the trino CLI.
    Returns results as list of dictionaries.
    """

    host: str = Field(
        default="localhost",
        description="Trino coordinator host"
    )

    port: int = Field(
        default=8080,
        description="Trino coordinator port"
    )

    catalog: str = Field(
        default="lakehouse",
        description="Default catalog to use"
    )

    schema: str = Field(
        default="payments_db",
        description="Default schema to use"
    )

    user: str = Field(
        default="dagster",
        description="Trino user"
    )

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a SQL query against Trino and return results.

        Args:
            query: SQL query string

        Returns:
            List of dictionaries, one per row

        Example:
            results = trino_resource.execute_query(
                "SELECT COUNT(*) as count FROM my_table"
            )
            print(results[0]['count'])
        """
        try:
            # Use trino CLI via subprocess
            # In production, use trino-python-client library
            cmd = [
                'trino',
                '--server', f'http://{self.host}:{self.port}',
                '--catalog', self.catalog,
                '--schema', self.schema,
                '--user', self.user,
                '--output-format', 'JSON',
                '--execute', query
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"Trino query failed: {result.stderr}")

            # Parse JSON output (one JSON object per line)
            rows = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    rows.append(json.loads(line))

            return rows

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Trino query timed out after 300 seconds")
        except FileNotFoundError:
            raise RuntimeError(
                "trino CLI not found. Install with: pip install trino-cli"
            )
        except Exception as e:
            raise RuntimeError(f"Trino query failed: {str(e)}")

    def execute_query_simple(self, query: str) -> str:
        """
        Execute a query and return raw output as string.

        Useful for simple queries where you just need the result text.

        Args:
            query: SQL query string

        Returns:
            Raw query output as string
        """
        cmd = [
            'trino',
            '--server', f'http://{self.host}:{self.port}',
            '--catalog', self.catalog,
            '--schema', self.schema,
            '--user', self.user,
            '--execute', query
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise RuntimeError(f"Trino query failed: {result.stderr}")

        return result.stdout.strip()

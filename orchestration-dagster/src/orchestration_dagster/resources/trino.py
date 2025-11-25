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
from trino.dbapi import connect
import os


class TrinoResource(ConfigurableResource):
    """
    Trino query resource for Dagster assets.

    Executes SQL queries against Trino using the trino Python client library.
    Returns results as list of dictionaries.
    """

    host: str = Field(
        default_factory=lambda: os.getenv("TRINO_HOST", "trino"),
        description="Trino coordinator host (set TRINO_HOST env var, defaults to 'trino' in K8s, 'localhost' locally)"
    )

    port: int = Field(
        default=8080,
        description="Trino coordinator port"
    )

    catalog: str = Field(
        default="iceberg",
        description="Default catalog to use (matches Trino catalog file name)"
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
            # Use trino Python client library
            with connect(
                host=self.host,
                port=self.port,
                catalog=self.catalog,
                schema=self.schema,
                user=self.user,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                # Get column names from cursor description
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                # Fetch all results and convert to list of dictionaries
                rows = []
                for row in cursor.fetchall():
                    if columns:
                        rows.append(dict(zip(columns, row)))
                    else:
                        # Fallback if no column names available
                        rows.append(row[0] if len(row) == 1 else row)

                cursor.close()
                return rows

        except Exception as e:
            raise RuntimeError(f"Trino query failed: {str(e)}")

    def execute_query_simple(self, query: str) -> str:
        """
        Execute a query and return raw output as string.

        Useful for simple queries where you just need the result text.
        Returns the first column of the first row as a string.

        Args:
            query: SQL query string

        Returns:
            Raw query output as string (first column of first row)
        """
        try:
            # Use trino Python client library
            with connect(
                host=self.host,
                port=self.port,
                catalog=self.catalog,
                schema=self.schema,
                user=self.user,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                # Get first row, first column
                row = cursor.fetchone()
                cursor.close()

                if row is None:
                    return ""

                # Return first column as string
                return str(row[0]) if row else ""

        except Exception as e:
            raise RuntimeError(f"Trino query failed: {str(e)}")

"""
PostgreSQL Resource for Dagster

Provides a reusable resource for reading payment events from the
PostgreSQL bronze layer and managing batch loading state.

Usage:
    @asset
    def my_asset(postgres_resource: PostgresResource):
        results = postgres_resource.execute_query("SELECT * FROM payment_events")
"""

from dagster import ConfigurableResource
from typing import List, Dict, Any
from datetime import date
from pydantic import Field
import psycopg
from psycopg.rows import dict_row
import os


class PostgresResource(ConfigurableResource):
    """
    PostgreSQL query resource for Dagster assets.

    Connects to the payment-pipeline PostgreSQL database to read
    enriched payment events for batch loading to Iceberg.
    """

    host: str = Field(
        default_factory=lambda: os.getenv("PAYMENTS_DB_HOST", "localhost"),
        description="PostgreSQL host (set PAYMENTS_DB_HOST env var)"
    )

    port: int = Field(
        default_factory=lambda: int(os.getenv("PAYMENTS_DB_PORT", "5432")),
        description="PostgreSQL port"
    )

    user: str = Field(
        default_factory=lambda: os.getenv("PAYMENTS_DB_USER", "payments"),
        description="PostgreSQL user"
    )

    password: str = Field(
        default_factory=lambda: os.getenv("PAYMENTS_DB_PASSWORD", "payments"),
        description="PostgreSQL password"
    )

    database: str = Field(
        default_factory=lambda: os.getenv("PAYMENTS_DB_NAME", "payments"),
        description="PostgreSQL database"
    )

    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query against PostgreSQL and return results.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of dictionaries, one per row

        Example:
            results = postgres_resource.execute_query(
                "SELECT * FROM payment_events WHERE loaded_to_iceberg = FALSE LIMIT %s",
                (100,)
            )
        """
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    return list(rows)
        except Exception as e:
            raise RuntimeError(f"PostgreSQL query failed: {str(e)}")

    def get_unloaded_events(self, table: str = "payment_events", limit: int = 10000) -> List[Dict[str, Any]]:
        """
        Get payment events that haven't been loaded to Iceberg yet.

        Args:
            table: Table name (payment_events or payment_events_quarantine)
            limit: Maximum number of records to fetch

        Returns:
            List of dictionaries with event data
        """
        query = f"""
            SELECT *
            FROM {table}
            WHERE loaded_to_iceberg = FALSE
            ORDER BY ingested_at ASC
            LIMIT %s
        """
        return self.execute_query(query, (limit,))

    def get_events_by_date(
        self,
        table: str = "payment_events",
        partition_date: date = None,
        limit: int = 50000,
    ) -> List[Dict[str, Any]]:
        """
        Get all payment events for a specific date (for backfill).

        Unlike get_unloaded_events, this queries ALL events for the date,
        not just unloaded ones. The Iceberg merge will handle deduplication.

        Args:
            table: Table name (payment_events or payment_events_quarantine)
            partition_date: Date to load events for
            limit: Maximum number of records to fetch

        Returns:
            List of dictionaries with event data
        """
        if partition_date is None:
            partition_date = date.today()

        query = f"""
            SELECT *
            FROM {table}
            WHERE DATE(ingested_at) = %s
            ORDER BY ingested_at ASC
            LIMIT %s
        """
        return self.execute_query(query, (partition_date, limit))

    def mark_as_loaded(self, table: str, event_ids: List[str]) -> int:
        """
        Mark events as loaded to Iceberg after successful batch processing.

        Args:
            table: Table name
            event_ids: List of event_id values to mark as loaded

        Returns:
            Number of rows updated
        """
        if not event_ids:
            return 0

        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    # Use ANY for list of IDs
                    cur.execute(
                        f"""
                        UPDATE {table}
                        SET loaded_to_iceberg = TRUE, loaded_at = NOW()
                        WHERE event_id = ANY(%s)
                        """,
                        (event_ids,)
                    )
                    updated = cur.rowcount
                    conn.commit()
                    return updated
        except Exception as e:
            raise RuntimeError(f"Failed to mark events as loaded: {str(e)}")

    def get_event_count(self, table: str = "payment_events", loaded: bool = None) -> int:
        """
        Get count of events in a table.

        Args:
            table: Table name
            loaded: If True, count loaded events; if False, count unloaded; if None, count all

        Returns:
            Count of events
        """
        if loaded is None:
            query = f"SELECT COUNT(*) as count FROM {table}"
            params = None
        else:
            query = f"SELECT COUNT(*) as count FROM {table} WHERE loaded_to_iceberg = %s"
            params = (loaded,)

        result = self.execute_query(query, params)
        return result[0]["count"] if result else 0

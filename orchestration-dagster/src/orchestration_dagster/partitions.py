"""Partition definitions for payment pipeline assets."""

from dagster import DailyPartitionsDefinition

# Daily partitions for backfill asset
# Start date is when payment pipeline first collected data
payment_daily_partitions = DailyPartitionsDefinition(
    start_date="2024-11-01",
    timezone="UTC",
)

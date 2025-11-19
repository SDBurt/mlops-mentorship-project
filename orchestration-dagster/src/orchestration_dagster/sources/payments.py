"""
Payment Data Quality Monitoring Assets

This module provides Dagster assets for monitoring quarantine tables
and alerting on data quality issues in the payment streaming pipeline.

Monitors:
- Quarantine volume by rejection reason
- Data quality trends over time
- Alert on volume spikes

Architecture:
- Queries Trino (Iceberg catalog) for quarantine tables
- Runs hourly to detect anomalies
- Logs warnings when quarantine volume exceeds thresholds
"""

from dagster import asset, AssetExecutionContext, MetadataValue
from typing import Dict, List, Any
import time


@asset(
    group_name="data_quality_payments",
    compute_kind="trino",
    description="Monitor quarantine_payment_charges for invalid records and alert on spikes"
)
def quarantine_charges_monitor(context: AssetExecutionContext, trino_resource) -> Dict[str, Any]:
    """
    Monitor quarantined charge events and alert on volume spikes.

    Queries the quarantine_payment_charges table to count invalid records
    by rejection reason in the last hour. Logs warnings if volume exceeds
    threshold (100 records/hour per reason).

    Returns:
        Dict with quarantine statistics and alerts
    """
    query = """
    SELECT
        rejection_reason,
        COUNT(*) as count,
        MIN(quarantine_timestamp) as first_seen,
        MAX(quarantine_timestamp) as last_seen
    FROM lakehouse.payments_db.quarantine_payment_charges
    WHERE quarantine_timestamp > current_timestamp - INTERVAL '1' HOUR
    GROUP BY rejection_reason
    ORDER BY count DESC
    """

    context.log.info("Querying quarantine_payment_charges for last hour...")
    results = trino_resource.execute_query(query)

    alerts = []
    total_quarantined = 0

    for row in results:
        reason = row['rejection_reason']
        count = row['count']
        total_quarantined += count

        # Alert threshold: 100 records/hour for single rejection reason
        if count > 100:
            alert_msg = f"HIGH QUARANTINE VOLUME: {count} '{reason}' in last hour"
            context.log.warning(alert_msg)
            alerts.append({
                'severity': 'warning',
                'reason': reason,
                'count': count,
                'message': alert_msg
            })
        else:
            context.log.info(f"Normal quarantine volume: {count} '{reason}'")

    # Log summary
    context.log.info(f"Total quarantined in last hour: {total_quarantined}")

    # Return metadata for Dagster UI
    return {
        'total_quarantined': total_quarantined,
        'breakdown': results,
        'alerts': alerts,
        'timestamp': time.time()
    }


@asset(
    group_name="data_quality_payments",
    compute_kind="trino",
    description="Monitor all payment quarantine tables (charges, refunds, disputes, subscriptions)"
)
def quarantine_summary_monitor(context: AssetExecutionContext, trino_resource) -> Dict[str, Any]:
    """
    Aggregate monitor for all payment quarantine tables.

    Provides a holistic view of data quality across all payment event types.
    Queries all 4 quarantine tables and aggregates statistics.

    Returns:
        Dict with summary statistics across all quarantine tables
    """
    tables = [
        'quarantine_payment_charges',
        'quarantine_payment_refunds',
        'quarantine_payment_disputes',
        'quarantine_payment_subscriptions'
    ]

    summary = {}
    total_all = 0

    for table in tables:
        query = f"""
        SELECT
            COUNT(*) as count,
            COUNT(DISTINCT rejection_reason) as unique_reasons
        FROM lakehouse.payments_db.{table}
        WHERE quarantine_timestamp > current_timestamp - INTERVAL '1' HOUR
        """

        context.log.info(f"Querying {table}...")
        result = trino_resource.execute_query(query)

        if result:
            count = result[0]['count']
            unique_reasons = result[0]['unique_reasons']
            total_all += count

            summary[table] = {
                'count': count,
                'unique_reasons': unique_reasons
            }

            context.log.info(f"{table}: {count} quarantined ({unique_reasons} unique reasons)")

    # Overall data quality score (percentage of valid records)
    # Assumes ~10,000 total events per hour across all types
    estimated_total = 10000
    data_quality_score = ((estimated_total - total_all) / estimated_total) * 100 if estimated_total > 0 else 100

    context.log.info(f"Total quarantined across all types: {total_all}")
    context.log.info(f"Estimated data quality score: {data_quality_score:.2f}%")

    # Alert if data quality < 99% (more than 1% invalid)
    if data_quality_score < 99.0:
        context.log.warning(
            f"DATA QUALITY ALERT: {data_quality_score:.2f}% quality "
            f"({total_all} invalid records in last hour)"
        )

    return {
        'summary': summary,
        'total_quarantined': total_all,
        'data_quality_score': data_quality_score,
        'timestamp': time.time()
    }


@asset(
    group_name="data_quality_payments",
    compute_kind="trino",
    description="Count validation flags in staging tables (suspicious patterns)"
)
def validation_flag_monitor(context: AssetExecutionContext, trino_resource) -> Dict[str, Any]:
    """
    Monitor validation_flag in staging tables.

    Tracks records that passed Flink validation but were flagged as suspicious
    by business rules (e.g., $0 charges, large amounts, missing failure codes).

    Returns:
        Dict with flagged record counts per table
    """
    query = """
    SELECT
        COUNT(*) as total_records,
        SUM(CASE WHEN validation_flag = true THEN 1 ELSE 0 END) as flagged_records,
        (SUM(CASE WHEN validation_flag = true THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as flagged_percentage
    FROM lakehouse.payments_db.payment_charges
    WHERE created_at > current_timestamp - INTERVAL '1' HOUR
    """

    context.log.info("Checking validation flags in payment_charges...")
    result = trino_resource.execute_query(query)

    if result:
        total = result[0]['total_records']
        flagged = result[0]['flagged_records']
        percentage = result[0]['flagged_percentage']

        context.log.info(
            f"Flagged records: {flagged}/{total} ({percentage:.2f}%)"
        )

        # Alert if >5% of records are flagged
        if percentage > 5.0:
            context.log.warning(
                f"HIGH SUSPICIOUS FLAG RATE: {percentage:.2f}% of charges flagged"
            )

        return {
            'total_records': total,
            'flagged_records': flagged,
            'flagged_percentage': percentage,
            'timestamp': time.time()
        }

    return {'error': 'No data found'}

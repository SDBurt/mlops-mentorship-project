from dagster import (
    Definitions,
    AssetSelection,
    AssetExecutionContext,
    asset,
    define_asset_job,
    ScheduleDefinition,
    DefaultScheduleStatus,
    MaterializeResult,
    RunRequest,
    schedule,
    MetadataValue,
)
import subprocess
import os
from pathlib import Path

from .defs.loads.reddit import create_reddit_source, create_reddit_pipeline
from .partitions import subreddit_partitions, SUBREDDITS


# Subreddit metadata asset (partitioned by subreddit)
@asset(
    name="reddit_subreddit",
    group_name="reddit",
    partitions_def=subreddit_partitions,
    compute_kind="dlt",
    pool="reddit_subreddit_metadata",  # Concurrency pool for metadata extraction
)
def reddit_subreddit_assets(context: AssetExecutionContext) -> MaterializeResult:
    """
    Reddit subreddit metadata (partitioned by subreddit).

    Each partition corresponds to a different subreddit.
    Extract metadata for the current partition's subreddit.
    """
    subreddit = context.partition_key

    # Create dlt source and pipeline dynamically based on partition
    # Resource names now include subreddit: reddit_{subreddit}_subreddit
    source = create_reddit_source(subreddit).with_resources(f"reddit_{subreddit}_subreddit")
    pipeline = create_reddit_pipeline(subreddit)

    # Run the dlt pipeline
    load_info = pipeline.run(source)

    # Return materialize result with metadata
    return MaterializeResult(
        metadata={
            "subreddit": subreddit,
            "pipeline_name": pipeline.pipeline_name,
            "load_id": load_info.load_packages[0].load_id if load_info.load_packages else "unknown",
        }
    )


# Posts and comments assets (partitioned by subreddit)
@asset(
    name="reddit_posts_comments",
    group_name="reddit",
    partitions_def=subreddit_partitions,
    compute_kind="dlt",
    pool="reddit_posts_comments",  # Concurrency pool for posts/comments extraction
)
def reddit_posts_comments_assets(context: AssetExecutionContext) -> MaterializeResult:
    """
    Reddit posts and comments (partitioned by subreddit).

    Each partition corresponds to a different subreddit.
    Extract top posts and their comments for the current partition's subreddit.
    """
    subreddit = context.partition_key

    # Create dlt source and pipeline dynamically based on partition
    # Resource names now include subreddit: reddit_{subreddit}_posts, reddit_{subreddit}_comments
    source = create_reddit_source(subreddit).with_resources(
        f"reddit_{subreddit}_posts",
        f"reddit_{subreddit}_comments"
    )
    pipeline = create_reddit_pipeline(subreddit)

    # Run the dlt pipeline
    load_info = pipeline.run(source)

    # Return materialize result with metadata
    return MaterializeResult(
        metadata={
            "subreddit": subreddit,
            "pipeline_name": pipeline.pipeline_name,
            "load_id": load_info.load_packages[0].load_id if load_info.load_packages else "unknown",
        }
    )


# DBT transformation asset (depends on all Reddit ingestion assets)
@asset(
    name="reddit_dbt_marts",
    group_name="reddit",
    compute_kind="dbt",
    deps=[reddit_posts_comments_assets],  # Depends on ingestion completing
)
def reddit_dbt_marts_asset(context: AssetExecutionContext) -> MaterializeResult:
    """
    DBT transformations for Reddit data.

    Runs `dbt build` which executes models and tests in dependency order:
    1. Staging models (views)
    2. Intermediate models (ephemeral)
    3. Marts models (dimensions and facts with incremental Iceberg tables)

    Runs after all Reddit posts/comments ingestion is complete.
    """
    # Get DBT project path (assuming it's in the repository)
    # Adjust path based on your actual directory structure
    dbt_project_path = Path(__file__).parent.parent.parent.parent / "transformations" / "dbt"

    context.log.info(f"Running DBT from: {dbt_project_path}")

    # Run dbt build (runs models + tests in dependency order)
    try:
        result = subprocess.run(
            ["dbt", "build", "--profiles-dir", str(dbt_project_path), "--target", "prod"],
            cwd=dbt_project_path,
            capture_output=True,
            text=True,
            check=True,
        )

        context.log.info(f"DBT stdout:\n{result.stdout}")

        # Parse DBT output for statistics (simplified)
        # In production, you'd want to parse the JSON output or use dagster-dbt
        models_built = result.stdout.count(" OK created")
        tests_passed = result.stdout.count(" PASS ")

        return MaterializeResult(
            metadata={
                "dbt_project_path": MetadataValue.text(str(dbt_project_path)),
                "models_built": MetadataValue.int(models_built),
                "tests_passed": MetadataValue.int(tests_passed),
                "stdout": MetadataValue.text(result.stdout[:1000]),  # First 1000 chars
            }
        )

    except subprocess.CalledProcessError as e:
        context.log.error(f"DBT build failed:\n{e.stderr}")
        raise RuntimeError(f"DBT build failed: {e.stderr}")


# Job for posts and comments (runs hourly)
# Each partition writes to its own tables, enabling full parallelism
reddit_posts_comments_job = define_asset_job(
    name="reddit_posts_comments_job",
    selection=AssetSelection.assets(reddit_posts_comments_assets),
    description="Ingest Reddit posts and comments (hourly)",
)

# Job for all Reddit assets (manual or daily)
# Each partition writes to its own tables, enabling full parallelism
reddit_full_job = define_asset_job(
    name="reddit_full_ingestion_job",
    selection=AssetSelection.groups("reddit"),
    description="Ingest all Reddit data: subreddit metadata, posts, and comments",
)

# Schedule to run posts/comments every hour (enabled by default)
# This will run ALL partitions (all subreddits) on each schedule tick
@schedule(
    name="reddit_hourly_schedule",
    job=reddit_posts_comments_job,
    cron_schedule="0 * * * *",  # Every hour at minute 0
    description="Run Reddit posts and comments ingestion for all subreddits every hour",
    default_status=DefaultScheduleStatus.RUNNING,  # Automatically enabled
)
def reddit_hourly_schedule():
    """
    Schedule function that runs all subreddit partitions every hour.

    Yields a RunRequest for each subreddit partition, ensuring all
    configured subreddits are processed on each schedule tick.
    """
    for subreddit in SUBREDDITS:
        yield RunRequest(
            run_key=f"reddit_{subreddit}",
            partition_key=subreddit,
            tags={
                "subreddit": subreddit,
                "schedule": "hourly",
            },
        )

# Define all assets and resources
defs = Definitions(
    assets=[
        reddit_subreddit_assets,
        reddit_posts_comments_assets,
        reddit_dbt_marts_asset,
    ],
    jobs=[
        reddit_posts_comments_job,
        reddit_full_job,
    ],
    schedules=[reddit_hourly_schedule],
    # Concurrency pool limits configured in dagster.yaml:
    # - reddit_subreddit_metadata: limit=5 (all subreddits run in parallel)
    # - reddit_posts_comments: limit=3 (max 3 concurrent extractions)
)

from dagster import (
    Definitions,
    AssetSelection,
    define_asset_job,
    ScheduleDefinition,
    DefaultScheduleStatus,
)

from .resources.iceberg import create_iceberg_io_manager
from .sources.reddit import reddit_posts, reddit_comments
# from .sources.reddit_pyarrow import reddit_posts_pyarrow, reddit_comments_pyarrow  # Uncomment for PyArrow


# Job for Reddit ingestion (Pandas backend)
reddit_ingestion_job = define_asset_job(
    name="reddit_ingestion_job",
    selection=AssetSelection.groups("reddit_ingestion"),
    description="Ingest Reddit posts and comments (Pandas backend)",
)

# Job for Reddit ingestion (PyArrow backend) - Uncomment to use
# reddit_ingestion_pyarrow_job = define_asset_job(
#     name="reddit_ingestion_pyarrow_job",
#     selection=AssetSelection.groups("reddit_ingestion_pyarrow"),
#     description="Ingest Reddit posts and comments (PyArrow backend)",
# )

# Define all assets and resources
defs = Definitions(
    assets=[
        # Pandas backend assets (default)
        reddit_posts,
        reddit_comments,

        # PyArrow backend assets (uncomment to use)
        # reddit_posts_pyarrow,
        # reddit_comments_pyarrow,
    ],
    resources={
        # Pandas backend (default) - best for small-to-medium datasets
        "iceberg_io_manager": create_iceberg_io_manager(
            namespace="data",
            backend="pandas"
        ),

        # PyArrow backend (uncomment to use) - best for large datasets
        # "iceberg_io_manager": create_iceberg_io_manager(
        #     namespace="data",
        #     backend="pyarrow"
        # ),
    },
    jobs=[
        reddit_ingestion_job,
        # reddit_ingestion_pyarrow_job,  # Uncomment for PyArrow
    ],
)

# Backend Selection Guide:
#
# Use Pandas backend (current default) when:
# - Dataset size < 1M rows
# - Team familiar with Pandas API
# - Need flexible data manipulation
# - Interactive exploration needed
#
# Use PyArrow backend when:
# - Dataset size > 1M rows
# - Performance is critical
# - Memory is constrained
# - Need columnar data format
#
# See BACKEND_COMPARISON.md for detailed comparison

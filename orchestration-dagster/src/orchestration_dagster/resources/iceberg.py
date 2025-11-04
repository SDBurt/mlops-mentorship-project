"""
Iceberg IO Manager Resource for Dagster.

Provides configured IO manager for writing Dagster assets to Apache Iceberg tables
via Apache Polaris REST catalog and MinIO S3 storage.

Supports both Pandas and PyArrow backends for flexibility.
"""

from dagster_iceberg.config import IcebergCatalogConfig
from dagster_iceberg.io_manager.pandas import PandasIcebergIOManager
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager
from typing import Union, Literal
import os


def create_iceberg_io_manager(
    namespace: str = "raw",
    backend: Literal["pandas", "pyarrow"] = "pandas",
    use_vended_credentials: bool = False
) -> Union[PandasIcebergIOManager, PyArrowIcebergIOManager]:
    """
    Create Iceberg IO manager with Apache Polaris catalog configuration.

    This IO manager automatically handles:
    - Table creation (schema inference from DataFrame/Table)
    - Partitioning (via asset metadata)
    - Schema evolution
    - Upserts/merges based on primary keys

    Args:
        namespace: Schema namespace for tables (default: "raw" for raw data layer)
        backend: Data format backend - "pandas" or "pyarrow" (default: "pandas")
        use_vended_credentials: Use Polaris vended credentials for S3 (AWS only, not MinIO)

    Returns:
        Configured PandasIcebergIOManager or PyArrowIcebergIOManager

    Environment Variables:
        PYICEBERG_CATALOG__DEFAULT__URI: Polaris REST API endpoint
        PYICEBERG_CATALOG__DEFAULT__CREDENTIAL: Polaris authentication (user:password)
        PYICEBERG_CATALOG__DEFAULT__S3__ENDPOINT: MinIO S3 endpoint
        PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID: MinIO access key
        PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY: MinIO secret key

    Backend Selection:
        - "pandas": Use PandasIcebergIOManager (assets return pd.DataFrame)
          Best for: Small-to-medium datasets, familiar API, interactive analysis

        - "pyarrow": Use PyArrowIcebergIOManager (assets return pa.Table)
          Best for: Large datasets, better performance, memory efficiency

    Examples:
        >>> # Pandas backend (default)
        >>> defs = Definitions(
        ...     resources={
        ...         "iceberg_io_manager": create_iceberg_io_manager(),
        ...     }
        ... )

        >>> # PyArrow backend for performance
        >>> defs = Definitions(
        ...     resources={
        ...         "iceberg_io_manager": create_iceberg_io_manager(backend="pyarrow"),
        ...     }
        ... )
    """
    # Get configuration from environment variables (set by set_pyiceberg_env.sh)
    # Defaults support both local development (localhost) and cluster deployment (service names)
    uri = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__URI",
        "http://polaris:8181/api/catalog"  # Cluster default (Polaris REST catalog)
    )

    credential = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__CREDENTIAL",
        "polaris_admin:polaris_admin_secret"  # Default bootstrap credentials
    )

    s3_endpoint = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__S3__ENDPOINT",
        "http://minio:9000"  # Cluster default
    )

    s3_access_key = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID",
        "admin"  # Default MinIO credentials (change for production)
    )

    s3_secret_key = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY",
        "minio123"  # Default MinIO credentials (change for production)
    )

    # Build catalog properties
    properties = {
        "uri": uri,
        "warehouse": "lakehouse",
        "type": "rest",
        # Authentication: Polaris uses OAuth2 with bootstrap credentials
        "credential": credential,
        "scope": "PRINCIPAL_ROLE:ALL",  # Required for Polaris OAuth2
        # S3/MinIO storage configuration
        "s3.endpoint": s3_endpoint,
        "s3.access-key-id": s3_access_key,
        "s3.secret-access-key": s3_secret_key,
        "s3.path-style-access": "true",
        "s3.region": "us-east-1",
        # Timestamp precision: Pandas uses ns, but Iceberg requires us
        "downcast-ns-timestamp-to-us-on-write": "true",
        # Use fsspec for direct S3 access (no write delegation)
        "py-io-impl": "pyiceberg.io.fsspec.FsspecFileIO",
        # Explicitly disable credential delegation - use client S3 credentials
        # This avoids Polaris permission errors for LOAD_TABLE_WITH_READ_DELEGATION
        "header.X-Iceberg-Access-Delegation": "false",
    }

    # Override with vended credentials if explicitly requested (AWS S3 only)
    if use_vended_credentials:
        properties["header.X-Iceberg-Access-Delegation"] = "vended-credentials"

    catalog_config = IcebergCatalogConfig(properties=properties)

    # Return appropriate IO manager based on backend
    if backend == "pyarrow":
        return PyArrowIcebergIOManager(
            name="lakehouse",
            config=catalog_config,
            namespace=namespace,
        )
    else:  # pandas (default)
        return PandasIcebergIOManager(
            name="lakehouse",
            config=catalog_config,
            namespace=namespace,
        )

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
    namespace: str = "data",
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
        namespace: Schema namespace for tables (default: "data" for single namespace)
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

    # Build credential from environment variables
    # IMPORTANT: These must be set after running 'make init-polaris'
    # The initialization script creates a dagster_user service account with proper RBAC
    polaris_client_id = os.getenv("POLARIS_CLIENT_ID")
    polaris_client_secret = os.getenv("POLARIS_CLIENT_SECRET")

    # Use PYICEBERG_CATALOG__DEFAULT__CREDENTIAL if set, otherwise build from individual vars
    credential = os.getenv("PYICEBERG_CATALOG__DEFAULT__CREDENTIAL")

    if not credential and polaris_client_id and polaris_client_secret:
        credential = f"{polaris_client_id}:{polaris_client_secret}"

    if not credential:
        raise ValueError(
            "Polaris credentials not configured. Please:\n"
            "1. Run: make init-polaris\n"
            "2. Source credentials: source infrastructure/kubernetes/polaris/.credentials/dagster_user.txt\n"
            "3. Update set_pyiceberg_env.sh with POLARIS_CLIENT_ID and POLARIS_CLIENT_SECRET\n"
            "4. Re-run: source set_pyiceberg_env.sh\n"
            "See infrastructure/kubernetes/polaris/SETUP.md for details."
        )

    s3_endpoint = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__S3__ENDPOINT",
        "http://minio:9000"  # Cluster default
    )

    s3_access_key = os.getenv(
        "PYICEBERG_CATALOG__DEFAULT__S3__ACCESS_KEY_ID",
        "admin"  # Default MinIO credentials (change for production)
    )

    # IMPORTANT: S3 secret key must be provided via environment variable
    # For production, use Kubernetes Secrets instead of hardcoded defaults
    s3_secret_key = os.getenv("PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY")
    if not s3_secret_key:
        raise ValueError(
            "PYICEBERG_CATALOG__DEFAULT__S3__SECRET_ACCESS_KEY environment variable must be set. "
            "Do not use hardcoded credentials in production."
        )

    # Get warehouse name from environment (catalog name in Polaris)
    warehouse = os.getenv("PYICEBERG_CATALOG__DEFAULT__WAREHOUSE", "lakehouse")
    if not warehouse:
        raise ValueError(
            "PYICEBERG_CATALOG__DEFAULT__WAREHOUSE environment variable must be set. "
            "This should match the catalog name created in Polaris."
        )

    # Get scope from environment (required for Polaris OAuth2)
    scope = os.getenv("PYICEBERG_CATALOG__DEFAULT__SCOPE", "PRINCIPAL_ROLE:ALL")

    # Build catalog properties
    properties = {
        "uri": uri,
        "warehouse": warehouse,
        "type": "rest",
        # Authentication: Polaris uses OAuth2 with bootstrap credentials
        "credential": credential,
        "scope": scope,  # Required for Polaris OAuth2
        # S3/MinIO storage configuration
        "s3.endpoint": s3_endpoint,
        "s3.access-key-id": s3_access_key,
        "s3.secret-access-key": s3_secret_key,
        "s3.path-style-access": "true",
        "s3.region": "us-east-1",
        # Timestamp precision: Pandas uses ns, but Iceberg requires us
        "downcast-ns-timestamp-to-us-on-write": "true",
    }

    # Add vended credentials header if explicitly requested (AWS S3 only, not MinIO)
    if use_vended_credentials:
        properties["header.X-Iceberg-Access-Delegation"] = "vended-credentials"

    catalog_config = IcebergCatalogConfig(properties=properties)

    # Return appropriate IO manager based on backend
    if backend == "pyarrow":
        return PyArrowIcebergIOManager(
            name=warehouse,
            config=catalog_config,
            namespace=namespace,
        )
    else:  # pandas (default)
        return PandasIcebergIOManager(
            name=warehouse,
            config=catalog_config,
            namespace=namespace,
        )

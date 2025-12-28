"""
Custom FileIO implementation for PyIceberg that forces localhost endpoint.

This is needed for local development with port-forwarding where Polaris
vends credentials with cluster DNS hostnames (minio) that need to be
resolved to localhost (127.0.0.1) in WSL2 environments.
"""
import os
from typing import Dict, Any
from pyiceberg.io.pyarrow import PyArrowFileIO


class LocalDevFileIO(PyArrowFileIO):
    """
    Custom FileIO that forces S3 endpoint to 127.0.0.1:9000.

    This allows local development with port-forwarding without modifying /etc/hosts.
    Overrides any S3 endpoint configuration from Polaris with localhost.
    """

    def __init__(self, properties: Dict[str, Any]):
        """Initialize FileIO with forced localhost endpoint."""
        # Force S3 endpoint to localhost for local development
        updated_properties = dict(properties)
        updated_properties["s3.endpoint"] = "http://127.0.0.1:9000"
        updated_properties["s3.path-style-access"] = "true"
        updated_properties["s3.region"] = "us-east-1"

        # Ensure credentials are set
        # IMPORTANT: These should be provided via environment variables
        # For production, use Kubernetes Secrets instead of hardcoded defaults
        if "s3.access-key-id" not in updated_properties:
            updated_properties["s3.access-key-id"] = os.getenv("AWS_ACCESS_KEY_ID", "admin")
        if "s3.secret-access-key" not in updated_properties:
            # Use environment variable or fail if not set (prevents accidental hardcoding)
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            if not secret_key:
                raise ValueError(
                    "AWS_SECRET_ACCESS_KEY environment variable must be set. "
                    "Do not use hardcoded credentials in production."
                )
            updated_properties["s3.secret-access-key"] = secret_key

        # Call parent with updated properties
        super().__init__(properties=updated_properties)

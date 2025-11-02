#!/usr/bin/env python3
"""
Test script to verify dlt can connect to Garage S3.
Run this before executing the full Dagster pipeline.
"""

import dlt


def test_s3_connection():
    """Test that dlt can connect to Garage S3 and write data."""
    print("Testing dlt filesystem destination with Garage S3...")

    # Create a simple test pipeline
    # Configuration is automatically loaded from .dlt/config.toml and .dlt/secrets.toml
    print("\n1. Creating test pipeline...")
    pipeline = dlt.pipeline(
        pipeline_name="s3_connection_test",
        destination="filesystem",
        dataset_name="test_connection",
        progress="log",
    )
    print(f"   ✓ Pipeline created: {pipeline.pipeline_name}")

    # Create simple test data
    print("\n2. Writing test data...")
    test_data = [
        {"id": 1, "message": "Hello from dlt"},
        {"id": 2, "message": "Testing Garage S3"},
        {"id": 3, "message": "Iceberg + merge coming soon"},
    ]

    try:
        load_info = pipeline.run(
            test_data,
            table_name="connection_test",
            write_disposition="replace",
        )
        print(f"   ✓ Data written successfully")
        print(f"   Load ID: {load_info.load_packages[0].load_id}")

        # Show what was loaded
        if load_info.load_packages:
            package = load_info.load_packages[0]
            print(f"\n3. Load package info:")
            print(f"   State: {package.state}")
            if hasattr(package, 'jobs'):
                for job in package.jobs:
                    print(f"   - Job: {job}")

        return True

    except Exception as e:
        print(f"   ✗ Write failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("DLT Garage S3 Connection Test")
    print("=" * 60)

    success = test_s3_connection()

    print("\n" + "=" * 60)
    if success:
        print("✓ SUCCESS: dlt can connect to Garage S3")
        print("\nNext steps:")
        print("1. Run the Dagster Reddit pipeline")
        print("2. Create Iceberg tables in Trino pointing to the Parquet files")
        print("3. Enable merge write disposition for ACID operations")
    else:
        print("✗ FAILED: Check configuration and Garage port-forward")
        print("\nTroubleshooting:")
        print("1. Verify port-forward is active: lsof -i :3900")
        print("2. Check .dlt/secrets.toml has correct credentials")
        print("3. Test Garage directly: curl http://localhost:3900")
    print("=" * 60)

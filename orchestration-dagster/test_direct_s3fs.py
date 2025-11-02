#!/usr/bin/env python3
"""
Test s3fs directly with Garage to isolate the configuration issue.
"""

import s3fs

# Garage credentials from secrets.toml
AWS_ACCESS_KEY = "GK8c71e502e22b1e1d88a43cd7"
AWS_SECRET_KEY = "30646052c9e3d801339f1979d817e3a2067192b4019b08a327c3cc0509bd5c33"
ENDPOINT = "http://localhost:3900"

print("Testing s3fs with Garage S3...")
print(f"Endpoint: {ENDPOINT}")
print(f"Bucket: lakehouse")
print()

try:
    # Create s3fs filesystem with Garage configuration
    # Garage requires AWS Signature Version 2 or specific region handling
    fs = s3fs.S3FileSystem(
        key=AWS_ACCESS_KEY,
        secret=AWS_SECRET_KEY,
        endpoint_url=ENDPOINT,
        client_kwargs={
            "region_name": "us-east-1",  # Standard AWS region instead of "garage"
        },
        config_kwargs={
            "s3": {
                "addressing_style": "path"  # Path-style addressing
            }
        },
        use_ssl=False,
    )

    print("1. Listing buckets...")
    buckets = fs.ls("/")
    print(f"   Found {len(buckets)} buckets: {buckets}")

    print("\n2. Listing lakehouse bucket...")
    contents = fs.ls("lakehouse")
    print(f"   Contents: {contents if contents else '(empty)'}")

    print("\n3. Testing write operation...")
    test_file = "lakehouse/test/hello.txt"
    fs.write_text(test_file, "Hello from s3fs!")
    print(f"   Written to {test_file}")

    print("\n4. Testing read operation...")
    content = fs.read_text(test_file)
    print(f"   Read: {content}")

    print("\n5. Cleanup...")
    fs.rm(test_file)
    print(f"   Deleted {test_file}")

    print("\nSUCCESS: s3fs can connect to Garage!")

except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

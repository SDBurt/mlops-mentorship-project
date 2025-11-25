# Use Flink 1.20, as Flink 2.0 doesn't have a compatible Iceberg version yet.
FROM flink:1.20-java17

# Install curl and netcat for health checks and job submission
USER root
RUN apt-get update && apt-get install -y curl netcat-openbsd && rm -rf /var/lib/apt/lists/*
USER flink

# Add Iceberg connector + Hadoop libraries + AWS SDK
# Unfortunately, the Iceberg Flink connector still requires Hadoop libraries
RUN cd /opt/flink/lib/ && \
    curl -LO https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime-1.20/1.9.1/iceberg-flink-runtime-1.20-1.9.1.jar && \
    curl -LO https://repo1.maven.org/maven2/org/apache/flink/flink-shaded-hadoop-2-uber/2.8.3-10.0/flink-shaded-hadoop-2-uber-2.8.3-10.0.jar && \
    curl -LO https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.31.9/bundle-2.31.9.jar

# Add Kafka connector
RUN cd /opt/flink/lib/ && \
    curl -LO https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.4.0-1.20/flink-sql-connector-kafka-3.4.0-1.20.jar

# Add S3 filesystem plugin (required for Iceberg/Polaris to write to MinIO)
# Plugins must be in their own subdirectory within /opt/flink/plugins/
USER root
RUN mkdir -p /opt/flink/plugins/s3-fs-hadoop && \
    cd /opt/flink/plugins/s3-fs-hadoop && \
    curl -LO https://repo1.maven.org/maven2/org/apache/flink/flink-s3-fs-hadoop/1.20.0/flink-s3-fs-hadoop-1.20.0.jar && \
    chown -R flink:flink /opt/flink/plugins
USER flink

# Copy auto-submission scripts (need root for /opt/flink)
USER root
COPY flink/entrypoint-submit.sh /opt/flink/entrypoint-submit.sh
RUN chmod +x /opt/flink/entrypoint-submit.sh
USER flink

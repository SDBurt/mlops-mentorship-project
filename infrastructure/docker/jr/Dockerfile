# Multi-stage build: Extract JR from official image
FROM jrndio/jr:latest AS jr-binary

# Use Kafka image as base (has all Kafka console tools)
FROM apache/kafka:4.0.0

USER root

# Copy JR binary from the jr-binary stage
COPY --from=jr-binary /bin/jr /usr/local/bin/jr
RUN chmod +x /usr/local/bin/jr

# Create directory for templates
RUN mkdir -p /home/jr-user/templates

# Copy all generation scripts
COPY generate-charges.sh /usr/local/bin/generate-charges.sh
COPY generate-refunds.sh /usr/local/bin/generate-refunds.sh
COPY generate-disputes.sh /usr/local/bin/generate-disputes.sh
COPY generate-subscriptions.sh /usr/local/bin/generate-subscriptions.sh
RUN chmod +x /usr/local/bin/generate-*.sh

USER appuser

# Default entrypoint (can be overridden in docker-compose.yml)
ENTRYPOINT ["/usr/local/bin/generate-charges.sh"]

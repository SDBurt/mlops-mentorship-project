#!/bin/bash
set -e
set -o pipefail

# Wait for Kafka to be ready
MAX_WAIT_SECONDS=${MAX_WAIT_SECONDS:-60}
START_TIME=$(date +%s)
echo "Waiting for Kafka broker to be ready (max ${MAX_WAIT_SECONDS}s)..."
until /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka-broker:29092 --list &>/dev/null; do
    ELAPSED=$(($(date +%s) - START_TIME))
    if [ $ELAPSED -ge $MAX_WAIT_SECONDS ]; then
        echo "ERROR: Kafka broker did not become ready within ${MAX_WAIT_SECONDS} seconds" >&2
        exit 1
    fi
    echo "Kafka not ready yet, waiting... (${ELAPSED}s elapsed)"
    sleep 2
done

# Check if template file exists and is readable
TEMPLATE_FILE="/home/jr-user/templates/payment_subscription.json"
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "ERROR: Template file not found: $TEMPLATE_FILE" >&2
    exit 1
fi
if [ ! -r "$TEMPLATE_FILE" ]; then
    echo "ERROR: Template file is not readable: $TEMPLATE_FILE" >&2
    exit 1
fi

echo "Kafka is ready! Starting payment subscription generation..."
echo "Generating events to topic: payment_subscriptions"
echo "Frequency: 6s (0.17 events/second)"
echo "Total events: 100,000"

# Generate events continuously and pipe to Kafka
# Use --oneline to output compact JSON (one object per line)
# QUIET_TIMING: if set to 'true', suppresses timing/progress messages on stderr
if [ "${QUIET_TIMING:-false}" = "true" ]; then
    jr run \
        --embedded "$(cat "$TEMPLATE_FILE")" \
        --num 100000 \
        --frequency 6s \
        --output stdout \
        --oneline 2> >(grep -v "^Elapsed\|^Data Generated\|^Throughput\|^timing" >&2) | \
    grep -v "^Elapsed\|^Data Generated\|^Throughput" | \
    /opt/kafka/bin/kafka-console-producer.sh \
        --bootstrap-server kafka-broker:29092 \
        --topic payment_subscriptions
else
    jr run \
        --embedded "$(cat "$TEMPLATE_FILE")" \
        --num 100000 \
        --frequency 6s \
        --output stdout \
        --oneline | \
    grep -v "^Elapsed\|^Data Generated\|^Throughput" | \
    /opt/kafka/bin/kafka-console-producer.sh \
        --bootstrap-server kafka-broker:29092 \
        --topic payment_subscriptions
fi

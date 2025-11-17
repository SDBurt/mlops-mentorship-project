#!/bin/bash
set -e

# Wait for Kafka to be ready
echo "Waiting for Kafka broker to be ready..."
until /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka-broker:29092 --list &>/dev/null; do
    echo "Kafka not ready yet, waiting..."
    sleep 2
done

echo "Kafka is ready! Starting payment charge generation..."
echo "Generating events to topic: payment_charges"
echo "Frequency: 2s (0.5 events/second)"
echo "Total events: 100,000"

# Generate events continuously and pipe to Kafka
# Use --embedded flag to read template from file, --oneline to output compact JSON (one object per line)
jr run \
    --embedded "$(cat /home/jr-user/templates/payment_charge.json)" \
    --num 100000 \
    --frequency 2s \
    --output stdout \
    --oneline 2>/dev/null | \
grep -v "^Elapsed\|^Data Generated\|^Throughput" | \
/opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka-broker:29092 \
    --topic payment_charges

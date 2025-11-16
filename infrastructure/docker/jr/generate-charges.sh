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
echo "Frequency: 500ms (2 events/second)"

# Generate events continuously and pipe to Kafka
jr run payment_charge \
    --jr_user_dir /home/jr-user/templates \
    --num 0 \
    --frequency 500ms \
    --output stdout | \
/opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka-broker:29092 \
    --topic payment_charges

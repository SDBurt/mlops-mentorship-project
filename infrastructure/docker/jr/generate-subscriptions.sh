#!/bin/bash
set -e

# Wait for Kafka to be ready
echo "Waiting for Kafka broker to be ready..."
until /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka-broker:29092 --list &>/dev/null; do
    echo "Kafka not ready yet, waiting..."
    sleep 2
done

echo "Kafka is ready! Starting payment subscription generation..."
echo "Generating events to topic: payment_subscriptions"
echo "Frequency: 3s"

# Generate events continuously and pipe to Kafka
jr run \
    --jr_user_dir /home/jr-user/templates \
    --embedded "$(cat /home/jr-user/templates/payment_subscription.json)" \
    --num 0 \
    --frequency 3s \
    --output stdout | \
/opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka-broker:29092 \
    --topic payment_subscriptions

#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Generating subscription events..."
echo "Topic: payment_subscriptions"
echo "Frequency: 3s"
echo "Press Ctrl+C to stop"
echo ""

jr run \
  --jr_user_dir "$SCRIPT_DIR" \
  --embedded "$(cat payment_subscription.json)" \
  --num 0 \
  --frequency 3s \
  --output kafka \
  --topic payment_subscriptions \
  --kafkaConfig kafka.client.properties

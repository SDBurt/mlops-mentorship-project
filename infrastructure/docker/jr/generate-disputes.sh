#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Generating payment dispute events..."
echo "Topic: payment_disputes"
echo "Frequency: 5s"
echo "Press Ctrl+C to stop"
echo ""

jr run \
  --jr_user_dir "$SCRIPT_DIR" \
  --embedded "$(cat payment_dispute.json)" \
  --num 0 \
  --frequency 5s \
  --output kafka \
  --topic payment_disputes \
  --kafkaConfig kafka.client.properties

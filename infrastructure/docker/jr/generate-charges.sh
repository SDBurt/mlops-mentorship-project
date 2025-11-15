#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Generating payment charge events..."
echo "Topic: payment_charges"
echo "Frequency: 500ms"
echo "Press Ctrl+C to stop"
echo ""

jr run \
  --jr_user_dir "$SCRIPT_DIR" \
  --embedded "$(cat payment_charge.json)" \
  --num 0 \
  --frequency 500ms \
  --output kafka \
  --topic payment_charges \
  --kafkaConfig kafka.client.properties

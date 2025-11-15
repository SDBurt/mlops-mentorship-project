#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Generating payment refund events..."
echo "Topic: payment_refunds"
echo "Frequency: 2s"
echo "Press Ctrl+C to stop"
echo ""

jr run \
  --jr_user_dir "$SCRIPT_DIR" \
  --embedded "$(cat payment_refund.json)" \
  --num 0 \
  --frequency 2s \
  --output kafka \
  --topic payment_refunds \
  --kafkaConfig kafka.client.properties

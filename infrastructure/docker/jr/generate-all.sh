#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting all payment event generators..."
echo ""

# Start charge events in background
echo "Starting charge events (500ms frequency)..."
./generate-charges.sh > /tmp/jr-charges.log 2>&1 &
CHARGES_PID=$!
echo "✓ Charges started (PID: $CHARGES_PID)"
echo ""

# Start refund events in background
echo "Starting refund events (2s frequency)..."
./generate-refunds.sh > /tmp/jr-refunds.log 2>&1 &
REFUNDS_PID=$!
echo "✓ Refunds started (PID: $REFUNDS_PID)"
echo ""

# Start dispute events in background
echo "Starting dispute events (5s frequency)..."
./generate-disputes.sh > /tmp/jr-disputes.log 2>&1 &
DISPUTES_PID=$!
echo "✓ Disputes started (PID: $DISPUTES_PID)"
echo ""

# Start subscription events in background
echo "Starting subscription events (3s frequency)..."
./generate-subscriptions.sh > /tmp/jr-subscriptions.log 2>&1 &
SUBSCRIPTIONS_PID=$!
echo "✓ Subscriptions started (PID: $SUBSCRIPTIONS_PID)"
echo ""

echo "=========================================="
echo "All event generators running in background!"
echo "=========================================="
echo ""
echo "Process IDs:"
echo "  Charges:       $CHARGES_PID"
echo "  Refunds:       $REFUNDS_PID"
echo "  Disputes:      $DISPUTES_PID"
echo "  Subscriptions: $SUBSCRIPTIONS_PID"
echo ""
echo "Logs available at:"
echo "  /tmp/jr-charges.log"
echo "  /tmp/jr-refunds.log"
echo "  /tmp/jr-disputes.log"
echo "  /tmp/jr-subscriptions.log"
echo ""
echo "Stop all generators:"
echo "  make jr-stop"
echo "  or: pkill -f 'jr run'"

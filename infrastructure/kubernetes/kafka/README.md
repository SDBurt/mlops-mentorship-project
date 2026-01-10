# Kafka (Bitnami Helm Chart)

Apache Kafka message broker for the payment pipeline. Uses KRaft mode (no ZooKeeper).

## Deployment

```bash
# Add Bitnami repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Install Kafka
helm install kafka bitnami/kafka -n lakehouse -f values.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kafka -n lakehouse --timeout=300s
```

## Topics

Pre-provisioned topics for the payment pipeline:

| Topic | Partitions | Purpose |
|-------|------------|---------|
| `webhooks.stripe.payment_intent` | 3 | Stripe payment intent webhooks |
| `webhooks.stripe.charge` | 3 | Stripe charge webhooks |
| `webhooks.stripe.refund` | 3 | Stripe refund webhooks |
| `payments.normalized` | 3 | Validated, normalized events |
| `payments.validation.dlq` | 1 | Dead letter queue |

## Service Access

### Internal (Kubernetes)

```
kafka.lakehouse.svc.cluster.local:9092
```

Or simplified within lakehouse namespace:
```
kafka:9092
```

### External (Port-Forward)

```bash
kubectl port-forward svc/kafka 9092:9092 -n lakehouse
```

Then connect to `localhost:9092`.

## Verification

```bash
# Check pods
kubectl get pods -n lakehouse -l app.kubernetes.io/name=kafka

# List topics
kubectl exec -n lakehouse kafka-controller-0 -- \
  kafka-topics.sh --list --bootstrap-server localhost:9092

# Describe a topic
kubectl exec -n lakehouse kafka-controller-0 -- \
  kafka-topics.sh --describe --topic payments.normalized --bootstrap-server localhost:9092
```

## Produce/Consume Test Messages

```bash
# Produce
kubectl exec -it -n lakehouse kafka-controller-0 -- \
  kafka-console-producer.sh --topic payments.normalized --bootstrap-server localhost:9092

# Consume
kubectl exec -it -n lakehouse kafka-controller-0 -- \
  kafka-console-consumer.sh --topic payments.normalized --from-beginning --bootstrap-server localhost:9092
```

## Configuration Notes

- **KRaft mode**: No ZooKeeper dependency (Kafka 3.x+)
- **Single broker**: Suitable for development, scale up for production
- **Auto-create topics**: Enabled for convenience
- **Retention**: 7 days for events, 30 days for DLQ
- **Persistence**: 5Gi volume, survives pod restarts

## Troubleshooting

### Pod not starting

Check events:
```bash
kubectl describe pod kafka-controller-0 -n lakehouse
kubectl logs kafka-controller-0 -n lakehouse
```

### Topic not created

Manually create:
```bash
kubectl exec -n lakehouse kafka-controller-0 -- \
  kafka-topics.sh --create --topic <topic-name> --partitions 3 --bootstrap-server localhost:9092
```

### Connection refused

Ensure port-forward is running and no other process uses port 9092.

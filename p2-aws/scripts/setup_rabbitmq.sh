#!/bin/bash
# Run this script ON the RabbitMQ EC2 after launch.
# Post-pivot version: only declares the queue + DLX. Lambdas read from
# RabbitMQ directly, so the SQS forwarder is no longer needed.

set -e

echo "=== Setting up RabbitMQ ==="

until docker exec rabbitmq rabbitmqctl status > /dev/null 2>&1; do
  echo "Waiting for RabbitMQ..."
  sleep 3
done

# Dead-letter exchange + queue (RabbitMQ-native — no SQS DLQ anymore).
docker exec rabbitmq rabbitmqadmin declare exchange name=ticket_dlx type=direct \
  --username=admin --password=admin123 2>/dev/null || true
docker exec rabbitmq rabbitmqadmin declare queue name=ticket_dlq durable=true \
  --username=admin --password=admin123 2>/dev/null || true
docker exec rabbitmq rabbitmqadmin declare binding source=ticket_dlx \
  destination=ticket_dlq routing_key=ticket_requests \
  --username=admin --password=admin123 2>/dev/null || true

# Main queue with DLX + max-priority so QUIT control messages can jump
# ahead if we ever want to (currently priority=255 on QUIT is honored
# only by consumers that opt into x-max-priority; without it QUIT just
# behaves as a normal message, which is fine).
docker exec rabbitmq rabbitmqadmin declare queue name=ticket_requests durable=true \
  arguments='{"x-dead-letter-exchange":"ticket_dlx","x-dead-letter-routing-key":"ticket_requests","x-max-priority":255}' \
  --username=admin --password=admin123

echo "=== RabbitMQ ready ==="
docker exec rabbitmq rabbitmqctl list_queues name messages

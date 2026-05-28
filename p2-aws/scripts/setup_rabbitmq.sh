#!/bin/bash
# Run this script ON the RabbitMQ EC2 after launch.
# Sets up RabbitMQ queues and the forwarder systemd service.

set -e

FORWARDER_DIR=/home/ec2-user/forwarder
SQS_QUEUE_URL=$1   # Pass as argument: ./setup_rabbitmq.sh https://sqs...

if [ -z "$SQS_QUEUE_URL" ]; then
  echo "Usage: $0 <SQS_QUEUE_URL>"
  exit 1
fi

echo "=== Setting up RabbitMQ ==="

# Wait for RabbitMQ to be ready
until docker exec rabbitmq rabbitmqctl status > /dev/null 2>&1; do
  echo "Waiting for RabbitMQ..."
  sleep 3
done

# Declare dead letter exchange and queue
docker exec rabbitmq rabbitmqctl add_vhost / 2>/dev/null || true
docker exec rabbitmq rabbitmqadmin declare exchange name=ticket_dlx type=direct \
  --username=admin --password=admin123 2>/dev/null || true
docker exec rabbitmq rabbitmqadmin declare queue name=ticket_dlq durable=true \
  --username=admin --password=admin123 2>/dev/null || true
docker exec rabbitmq rabbitmqadmin declare binding source=ticket_dlx \
  destination=ticket_dlq routing_key=ticket_requests \
  --username=admin --password=admin123 2>/dev/null || true

# Declare main queue with DLX
docker exec rabbitmq rabbitmqadmin declare queue name=ticket_requests durable=true \
  arguments='{"x-dead-letter-exchange":"ticket_dlx","x-dead-letter-routing-key":"ticket_requests"}' \
  --username=admin --password=admin123

echo "=== Installing forwarder ==="
pip3 install pika boto3

mkdir -p $FORWARDER_DIR
cp /home/ec2-user/forwarder.py $FORWARDER_DIR/ 2>/dev/null || true

# Write environment file
AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
cat > /etc/forwarder.env <<EOF
RABBITMQ_HOST=localhost
RABBITMQ_USER=admin
RABBITMQ_PASS=admin123
RABBITMQ_QUEUE=ticket_requests
SQS_QUEUE_URL=${SQS_QUEUE_URL}
AWS_REGION=${AWS_REGION}
BATCH_SIZE=10
EOF

# Install and start systemd service
cp /home/ec2-user/forwarder.service /etc/systemd/system/forwarder.service
systemctl daemon-reload
systemctl enable forwarder
systemctl start forwarder

echo "=== RabbitMQ + forwarder setup complete ==="
systemctl status forwarder

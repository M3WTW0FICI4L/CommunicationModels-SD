#!/bin/bash
# One-command deploy. Run from p2-aws/infra/ directory.
# Prerequisites: AWS CLI configured, CDK bootstrapped, key pair created in AWS.
set -e

REGION=${AWS_DEFAULT_REGION:-us-east-1}
KEY_NAME=${KEY_NAME:-ticket-key}

echo "=== Deploying Ticket Service Stack ==="
echo "Region: $REGION | Key: $KEY_NAME"

cd "$(dirname "$0")/../infra"

# Install CDK dependencies
pip install -r requirements.txt -q

# Install Lambda dependencies into asset directory
echo "Packaging Lambda..."
pip install -r ../src/lambda_worker/requirements.txt \
  -t ../src/lambda_worker/ --quiet

# Deploy
cdk deploy \
  --context region="$REGION" \
  --context key_name="$KEY_NAME" \
  --outputs-file ../config/stack_outputs.json \
  --require-approval never

echo ""
echo "=== Stack deployed. Outputs: ==="
cat ../config/stack_outputs.json

# Extract outputs
RABBITMQ_HOST=$(python3 -c "import json; d=json.load(open('../config/stack_outputs.json')); print(d['TicketServiceStack']['RabbitMQHost'])")
POSTGRES_HOST=$(python3 -c "import json; d=json.load(open('../config/stack_outputs.json')); print(d['TicketServiceStack']['PostgresHost'])")
SQS_URL=$(python3 -c "import json; d=json.load(open('../config/stack_outputs.json')); print(d['TicketServiceStack']['SQSQueueUrl'])")
LAMBDA_NAME=$(python3 -c "import json; d=json.load(open('../config/stack_outputs.json')); print(d['TicketServiceStack']['LambdaFunctionName'])")

echo ""
echo "=== Next steps ==="
echo "1. Wait ~3 min for EC2 instances to initialize"
echo "2. SSH to PostgreSQL and run:"
echo "   scp scripts/setup_postgres.sh ec2-user@${POSTGRES_HOST}:~/"
echo "   ssh ec2-user@${POSTGRES_HOST} 'bash setup_postgres.sh'"
echo ""
echo "3. Copy forwarder files and SSH to RabbitMQ:"
echo "   scp src/forwarder/forwarder.py src/forwarder/forwarder.service ec2-user@${RABBITMQ_HOST}:~/"
echo "   ssh ec2-user@${RABBITMQ_HOST} 'bash setup_rabbitmq.sh ${SQS_URL}'"
echo ""
echo "4. Set environment and run experiments:"
echo "   export RABBITMQ_HOST=${RABBITMQ_HOST}"
echo "   export SQS_QUEUE_URL=${SQS_URL}"
echo "   export LAMBDA_FUNCTION_NAME=${LAMBDA_NAME}"
echo "   export PG_HOST=${POSTGRES_HOST}"

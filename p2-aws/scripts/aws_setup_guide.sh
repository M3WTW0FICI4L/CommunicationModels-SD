#!/bin/bash
# AWS CLI + CDK setup guide — run once before deploying.
# This script prints instructions; it does not make AWS calls.

cat <<'GUIDE'
=============================================================
 AWS CLI + CDK Setup (one-time)
=============================================================

STEP 1 — Install AWS CLI v2
  Windows (PowerShell as admin):
    msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

  Mac/Linux:
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
    unzip awscliv2.zip && sudo ./aws/install

  Verify: aws --version

STEP 2 — Configure credentials from the AWS Academy / student account
  aws configure
    AWS Access Key ID:     <from AWS Academy "AWS Details" button>
    AWS Secret Access Key: <same>
    Default region:        us-east-1
    Default output format: json

  If using AWS Academy (session tokens):
    aws configure set aws_session_token <SESSION_TOKEN>

STEP 3 — Install Node.js (required for CDK)
  https://nodejs.org/ → LTS version
  Verify: node --version

STEP 4 — Install AWS CDK
  npm install -g aws-cdk
  Verify: cdk --version

STEP 5 — Bootstrap CDK in your account (one-time per region)
  cd p2-aws/infra
  pip install -r requirements.txt
  cdk bootstrap aws://ACCOUNT_ID/us-east-1

  Get your account ID: aws sts get-caller-identity --query Account --output text

STEP 6 — Create an EC2 key pair (to SSH into instances)
  aws ec2 create-key-pair \
    --key-name ticket-key \
    --query 'KeyMaterial' \
    --output text > ticket-key.pem
  chmod 400 ticket-key.pem   # Linux/Mac only

STEP 7 — Deploy
  cd p2-aws
  bash scripts/deploy.sh

STEP 8 — After experiments, DESTROY to stop billing!
  bash scripts/teardown.sh

=============================================================
 Cost estimate (€50 budget)
=============================================================
  EC2 t3.small (RabbitMQ):  ~€0.019/hr  → €0.46/day
  EC2 t3.micro (PostgreSQL): ~€0.010/hr → €0.24/day
  Lambda invocations:         essentially free (free tier)
  SQS:                        first 1M/month free
  CloudWatch:                 first 10 custom metrics free
  TOTAL running cost:         ~€0.70/day

  IMPORTANT: Stop EC2 instances when not running experiments!
    aws ec2 stop-instances --instance-ids i-xxxx i-yyyy

GUIDE

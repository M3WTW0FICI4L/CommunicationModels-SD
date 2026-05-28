#!/usr/bin/env python3
"""CDK app entry point.

Uses CliCredentialsStackSynthesizer to skip the `cdk bootstrap` step, which
fails in AWS Academy Learner Lab because the lab role cannot create new IAM
roles. Instead, CDK uses the caller's CLI credentials directly and uploads
Lambda assets to a pre-existing S3 bucket.
"""
import os
import aws_cdk as cdk
from stacks.ticket_stack import TicketServiceStack

app = cdk.App()

account = (
    app.node.try_get_context("account")
    or os.environ.get("CDK_DEFAULT_ACCOUNT")
)
if not account:
    raise SystemExit("No AWS account ID. Set CDK_DEFAULT_ACCOUNT or pass -c account=...")
region = (
    app.node.try_get_context("region")
    or os.environ.get("CDK_DEFAULT_REGION")
    or "us-east-1"
)
assets_bucket = (
    app.node.try_get_context("assets_bucket")
    or f"ticket-cdk-assets-{account}"
)

TicketServiceStack(
    app,
    "TicketServiceStack",
    env=cdk.Environment(account=account, region=region),
    synthesizer=cdk.CliCredentialsStackSynthesizer(
        file_assets_bucket_name=assets_bucket,
        bucket_prefix="lambda-assets/",
    ),
)
app.synth()

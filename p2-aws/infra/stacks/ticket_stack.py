"""CDK stack — post-SQS-pivot version.

Architecture:
  Client -> RabbitMQ (EC2) -> Lambda workers (invoked on demand by the
  scaler, which runs on the VM) -> PostgreSQL (EC2).

There is no SQS or DLQ. The scaler converges the number of alive Lambda
workers to N = (B + lambda*Tr) / (C*Tr) by either invoking new Lambdas
or publishing QUIT control messages to the RabbitMQ queue.

AWS Academy Learner Lab constraints (account 523786088090):
  - Cannot create IAM roles -> reuse LabRole and LabInstanceProfile.
  - cdk bootstrap cannot create its toolkit roles -> use
    CliCredentialsStackSynthesizer with a pre-created assets bucket.
  - Use ec2.CfnInstance so CDK does not try to create a default
    instance role.
"""
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cloudwatch as cw,
    aws_s3 as s3,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class TicketServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        lab_role_arn = f"arn:aws:iam::{self.account}:role/LabRole"
        lab_role = iam.Role.from_role_arn(
            self, "LabRole", lab_role_arn, mutable=False
        )
        lab_instance_profile_name = "LabInstanceProfile"

        # ── VPC ──────────────────────────────────────────────────────────────
        vpc = ec2.Vpc(
            self, "TicketVpc",
            max_azs=1,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
        )
        public_subnet = vpc.public_subnets[0]

        # ── Security Groups ───────────────────────────────────────────────────
        sg_rabbitmq = ec2.SecurityGroup(
            self, "SgRabbitMQ", vpc=vpc, description="RabbitMQ EC2"
        )
        sg_rabbitmq.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(5672), "AMQP")
        sg_rabbitmq.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(15672), "Mgmt UI")
        sg_rabbitmq.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        sg_postgres = ec2.SecurityGroup(
            self, "SgPostgres", vpc=vpc, description="PostgreSQL EC2"
        )
        sg_postgres.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(5432), "PostgreSQL")
        sg_postgres.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        key_name = self.node.try_get_context("key_name") or "ticket-key"

        ami = ec2.MachineImage.latest_amazon_linux2(
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE,
        )
        ami_id = ami.get_image(self).image_id

        # ── RabbitMQ EC2 ──────────────────────────────────────────────────────
        rabbitmq_userdata = ec2.UserData.for_linux()
        rabbitmq_userdata.add_commands(
            "yum update -y",
            "yum install -y python3-pip docker",
            "systemctl enable docker && systemctl start docker",
            "docker run -d --name rabbitmq --restart always "
            "-p 5672:5672 -p 15672:15672 "
            "-e RABBITMQ_DEFAULT_USER=admin "
            "-e RABBITMQ_DEFAULT_PASS=admin123 "
            "rabbitmq:3.13-management-alpine",
            "pip3 install pika boto3",
        )

        self.rabbitmq_ec2 = ec2.CfnInstance(
            self, "RabbitMQInstance",
            instance_type="t3.small",
            image_id=ami_id,
            key_name=key_name,
            subnet_id=public_subnet.subnet_id,
            security_group_ids=[sg_rabbitmq.security_group_id],
            iam_instance_profile=lab_instance_profile_name,
            user_data=cdk.Fn.base64(rabbitmq_userdata.render()),
            tags=[cdk.CfnTag(key="Name", value="TicketRabbitMQ")],
        )

        # ── PostgreSQL EC2 ────────────────────────────────────────────────────
        postgres_userdata = ec2.UserData.for_linux()
        postgres_userdata.add_commands(
            "yum update -y",
            "amazon-linux-extras enable postgresql14",
            "yum clean metadata",
            "yum install -y postgresql postgresql-server",
            "postgresql-setup --initdb",
            "systemctl enable postgresql",
            "systemctl start postgresql",
        )

        self.postgres_ec2 = ec2.CfnInstance(
            self, "PostgresInstance",
            instance_type="t3.micro",
            image_id=ami_id,
            key_name=key_name,
            subnet_id=public_subnet.subnet_id,
            security_group_ids=[sg_postgres.security_group_id],
            iam_instance_profile=lab_instance_profile_name,
            user_data=cdk.Fn.base64(postgres_userdata.render()),
            tags=[cdk.CfnTag(key="Name", value="TicketPostgres")],
        )

        # ── S3 results bucket ────────────────────────────────────────────────
        results_bucket = s3.Bucket(
            self, "ResultsBucket",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── Lambda worker ────────────────────────────────────────────────────
        # Reads from RabbitMQ directly. Invoked on demand by the scaler.
        # Long-running (up to ~14 min) until QUIT, idle timeout, or safety
        # margin before Lambda hard-timeout.
        self.worker_lambda = lambda_.Function(
            self, "TicketWorker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../src/lambda_worker"),
            timeout=Duration.seconds(870),  # max 15 min; leave headroom
            memory_size=256,
            role=lab_role,
            environment={
                "RABBITMQ_HOST": self.rabbitmq_ec2.attr_public_ip,
                "RABBITMQ_USER": "admin",
                "RABBITMQ_PASS": "admin123",
                "RABBITMQ_QUEUE": "ticket_requests",
                "PG_HOST": self.postgres_ec2.attr_public_ip,
                "PG_PORT": "5432",
                "PG_DB": "tickets",
                "PG_USER": "ticket_user",
                "PG_PASS": "ticket_pass",
                "RESULTS_BUCKET": results_bucket.bucket_name,
                "MAX_UNNUMBERED": "100000",
                "MAX_SEATS": "100000",
                "IDLE_TIMEOUT_S": "20",
                "SAFETY_MARGIN_S": "30",
            },
        )

        # ── CloudWatch dashboard ─────────────────────────────────────────────
        dashboard = cw.Dashboard(
            self, "TicketDashboard", dashboard_name="TicketService"
        )
        dashboard.add_widgets(
            cw.GraphWidget(
                title="Queue Backlog (RabbitMQ)",
                left=[
                    cw.Metric(
                        namespace="TicketService",
                        metric_name="QueueBacklog",
                        period=Duration.seconds(10),
                        statistic="Maximum",
                    )
                ],
            ),
            cw.GraphWidget(
                title="Target / Alive Workers",
                left=[
                    cw.Metric(
                        namespace="TicketService",
                        metric_name="TargetWorkers",
                        period=Duration.seconds(10),
                        statistic="Maximum",
                    )
                ],
            ),
            cw.GraphWidget(
                title="Arrival Rate (msgs/s)",
                left=[
                    cw.Metric(
                        namespace="TicketService",
                        metric_name="ArrivalRate",
                        period=Duration.seconds(10),
                        statistic="Average",
                    )
                ],
            ),
            cw.GraphWidget(
                title="Processing Latency p99 (ms)",
                left=[
                    cw.Metric(
                        namespace="TicketService",
                        metric_name="ProcessingLatencyMs",
                        period=Duration.seconds(10),
                        statistic="p99",
                    )
                ],
            ),
        )

        # ── Outputs ──────────────────────────────────────────────────────────
        CfnOutput(self, "RabbitMQHost", value=self.rabbitmq_ec2.attr_public_ip)
        CfnOutput(self, "PostgresHost", value=self.postgres_ec2.attr_public_ip)
        CfnOutput(self, "LambdaFunctionName", value=self.worker_lambda.function_name)
        CfnOutput(self, "ResultsBucketName", value=results_bucket.bucket_name)

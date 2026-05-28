import os
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_sqs as sqs,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_es,
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

        # ── VPC ──────────────────────────────────────────────────────────────
        vpc = ec2.Vpc(self, "TicketVpc",
            max_azs=1,
            nat_gateways=0,  # avoid NAT gateway cost
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
            ],
        )

        # ── Security Groups ───────────────────────────────────────────────────
        sg_rabbitmq = ec2.SecurityGroup(self, "SgRabbitMQ", vpc=vpc, description="RabbitMQ EC2")
        sg_rabbitmq.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(5672), "AMQP")
        sg_rabbitmq.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(15672), "Management UI")
        sg_rabbitmq.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        sg_postgres = ec2.SecurityGroup(self, "SgPostgres", vpc=vpc, description="PostgreSQL EC2")
        sg_postgres.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(5432), "PostgreSQL")
        sg_postgres.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        # ── Key pair (must be pre-created in AWS console) ─────────────────────
        key_name = self.node.try_get_context("key_name") or "ticket-key"

        # ── User data: RabbitMQ EC2 ───────────────────────────────────────────
        rabbitmq_userdata = ec2.UserData.for_linux()
        rabbitmq_userdata.add_commands(
            "yum update -y",
            "yum install -y python3-pip",
            # Install RabbitMQ via Docker for simplicity
            "yum install -y docker",
            "systemctl enable docker && systemctl start docker",
            "docker run -d --name rabbitmq --restart always "
            "  -p 5672:5672 -p 15672:15672 "
            "  -e RABBITMQ_DEFAULT_USER=admin "
            "  -e RABBITMQ_DEFAULT_PASS=admin123 "
            "  rabbitmq:3.13-management-alpine",
            # Install forwarder dependencies
            "pip3 install pika boto3",
            # The forwarder script is uploaded separately via SSM/SCP
        )

        # ── EC2: RabbitMQ (t3.small for management UI overhead) ──────────────
        self.rabbitmq_ec2 = ec2.Instance(self, "RabbitMQInstance",
            instance_type=ec2.InstanceType("t3.small"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg_rabbitmq,
            key_name=key_name,
            user_data=rabbitmq_userdata,
        )
        # Allow RabbitMQ EC2 to publish to SQS
        self.rabbitmq_ec2.add_to_role_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage", "sqs:GetQueueAttributes", "cloudwatch:PutMetricData"],
            resources=["*"],
        ))

        # ── User data: PostgreSQL EC2 ─────────────────────────────────────────
        # Only installs PostgreSQL; schema setup done via scripts/setup_postgres.sh
        postgres_userdata = ec2.UserData.for_linux()
        postgres_userdata.add_commands(
            "yum update -y",
            "amazon-linux-extras enable postgresql14",
            "yum install -y postgresql14-server postgresql14",
            "postgresql-setup --initdb",
            "systemctl enable postgresql",
            "systemctl start postgresql",
        )

        self.postgres_ec2 = ec2.Instance(self, "PostgresInstance",
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg_postgres,
            key_name=key_name,
            user_data=postgres_userdata,
        )

        # ── SQS: Dead Letter Queue ────────────────────────────────────────────
        dlq = sqs.Queue(self, "TicketDLQ",
            queue_name="ticket-dlq",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── SQS: Main Queue ───────────────────────────────────────────────────
        self.main_queue = sqs.Queue(self, "TicketQueue",
            queue_name="ticket-requests",
            visibility_timeout=Duration.seconds(30),  # > lambda timeout
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── S3: Results/logs bucket ───────────────────────────────────────────
        results_bucket = s3.Bucket(self, "ResultsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── Lambda: worker ────────────────────────────────────────────────────
        worker_role = iam.Role(self, "LambdaWorkerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        worker_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes",
                "cloudwatch:PutMetricData",
                "s3:PutObject",
            ],
            resources=["*"],
        ))

        self.worker_lambda = lambda_.Function(self, "TicketWorker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../src/lambda_worker"),
            timeout=Duration.seconds(20),
            memory_size=256,
            role=worker_role,
            reserved_concurrent_executions=1,  # start with 1, scaler adjusts
            environment={
                "PG_HOST": self.postgres_ec2.instance_public_ip,
                "PG_PORT": "5432",
                "PG_DB": "tickets",
                "PG_USER": "ticket_user",
                "PG_PASS": "ticket_pass",
                "RESULTS_BUCKET": results_bucket.bucket_name,
                "MAX_UNNUMBERED": "100000",
                "MAX_SEATS": "100000",
            },
        )

        # SQS triggers Lambda (batch size 10, auto-scales concurrency)
        self.worker_lambda.add_event_source(
            lambda_es.SqsEventSource(self.main_queue, batch_size=10)
        )

        # ── CloudWatch Dashboard ──────────────────────────────────────────────
        dashboard = cw.Dashboard(self, "TicketDashboard", dashboard_name="TicketService")
        dashboard.add_widgets(
            cw.GraphWidget(
                title="SQS Queue Depth",
                left=[self.main_queue.metric_approximate_number_of_messages_visible(
                    period=Duration.seconds(10),
                    statistic="Maximum",
                )],
            ),
            cw.GraphWidget(
                title="Lambda Concurrency",
                left=[self.worker_lambda.metric_concurrent_executions(
                    period=Duration.seconds(10),
                )],
            ),
            cw.GraphWidget(
                title="Lambda Duration (ms)",
                left=[self.worker_lambda.metric_duration(
                    period=Duration.seconds(10),
                    statistic="p99",
                )],
            ),
            cw.GraphWidget(
                title="DLQ Messages",
                left=[dlq.metric_approximate_number_of_messages_visible(
                    period=Duration.seconds(30),
                )],
            ),
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "RabbitMQHost", value=self.rabbitmq_ec2.instance_public_ip)
        CfnOutput(self, "PostgresHost", value=self.postgres_ec2.instance_public_ip)
        CfnOutput(self, "SQSQueueUrl", value=self.main_queue.queue_url)
        CfnOutput(self, "LambdaFunctionName", value=self.worker_lambda.function_name)
        CfnOutput(self, "ResultsBucketName", value=results_bucket.bucket_name)

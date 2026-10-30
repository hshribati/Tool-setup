"""Create AWS clients using boto3."""

import boto3


class AWSClients:
    """Keep the AWS service clients in one place."""

    def __init__(self, region: str):
        self.region = region
        self.ec2 = boto3.client("ec2", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)
        self.iam = boto3.client("iam", region_name=region)
        self.elbv2 = boto3.client("elbv2", region_name=region)
        self.autoscaling = boto3.client("autoscaling", region_name=region)

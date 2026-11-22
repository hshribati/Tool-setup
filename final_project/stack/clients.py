
"""AWS service clients for the Final Weather Advisor project."""

import boto3


class AWSClients:
    """Keep AWS service clients in one place."""

    def __init__(self, region: str):
        self.region = region

        self.ec2 = boto3.client("ec2", region_name=region)
        self.iam = boto3.client("iam", region_name=region)
        self.elbv2 = boto3.client("elbv2", region_name=region)
        self.autoscaling = boto3.client(
            "autoscaling", region_name=region
        )
        self.sts = boto3.client("sts", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        self.dynamodb = boto3.client(
            "dynamodb", region_name=region
        )
        self.sns = boto3.client("sns", region_name=region)

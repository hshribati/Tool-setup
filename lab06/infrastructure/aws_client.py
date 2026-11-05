import boto3

AWS_REGION = "us-east-2"

def get_ec2_client():
    return boto3.client("ec2", region_name=AWS_REGION)

def get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)

def get_elbv2_client():
    return boto3.client("elbv2", region_name=AWS_REGION)

def get_autoscaling_client():
    return boto3.client("autoscaling", region_name=AWS_REGION)

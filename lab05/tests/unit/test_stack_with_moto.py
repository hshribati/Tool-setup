"""Test AWS resource functions using moto."""

import boto3
from moto import mock_aws

from stack.storage import (
    create_bucket,
    create_instance_profile,
    create_role,
)
from stack.policies import uploader_policy


@mock_aws
def test_create_bucket():
    s3 = boto3.client("s3", region_name="us-east-2")

    create_bucket(s3, "lab05-test-bucket", "us-east-2")

    names = [
        bucket["Name"]
        for bucket in s3.list_buckets()["Buckets"]
    ]

    assert "lab05-test-bucket" in names


@mock_aws
def test_create_role():
    iam = boto3.client("iam", region_name="us-east-2")

    create_role(
        iam,
        "Lab05TestRole",
        uploader_policy("lab05-test-bucket"),
    )

    role = iam.get_role(RoleName="Lab05TestRole")

    assert role["Role"]["RoleName"] == "Lab05TestRole"


@mock_aws
def test_create_instance_profile():
    iam = boto3.client("iam", region_name="us-east-2")

    create_role(
        iam,
        "Lab05TestRole",
        uploader_policy("lab05-test-bucket"),
    )

    create_instance_profile(
        iam,
        "Lab05TestProfile",
        "Lab05TestRole",
    )

    profile = iam.get_instance_profile(
        InstanceProfileName="Lab05TestProfile"
    )["InstanceProfile"]

    assert profile["Roles"][0]["RoleName"] == "Lab05TestRole"


@mock_aws
def test_create_launch_template():
    from stack.compute import create_launch_template
    from stack.config import Settings

    settings = Settings.from_file(".env")
    ec2 = boto3.client("ec2", region_name=settings.region)

    template_id = create_launch_template(
        ec2, settings.uploader, settings
    )

    response = ec2.describe_launch_templates(
        LaunchTemplateIds=[template_id]
    )

    assert len(response["LaunchTemplates"]) == 1


@mock_aws
def test_get_network():
    from stack.network import get_network
    from stack.config import Settings

    settings = Settings.from_file(".env")
    ec2 = boto3.client("ec2", region_name=settings.region)

    vpc_id, subnet_ids = get_network(ec2, settings)

    assert vpc_id.startswith("vpc-")
    assert len(subnet_ids) == 2


@mock_aws
def test_create_asg():
    from stack.scaling import create_asg
    from stack.config import Settings

    settings = Settings.from_file(".env")

    ec2 = boto3.client("ec2", region_name=settings.region)
    autoscaling = boto3.client("autoscaling", region_name=settings.region)

    ec2.create_launch_template(
        LaunchTemplateName=settings.uploader.lt_name,
        LaunchTemplateData={
            "ImageId": settings.ami_id,
            "InstanceType": settings.instance_type,
        },
    )

    subnets = ec2.describe_subnets()["Subnets"]
    subnet_ids = [subnet["SubnetId"] for subnet in subnets[:2]]

    elbv2 = boto3.client("elbv2", region_name=settings.region)

    vpc_id = ec2.describe_vpcs()["Vpcs"][0]["VpcId"]

    target_group = elbv2.create_target_group(
        Name="lab05-test-target",
        Protocol="HTTP",
        Port=3000,
        VpcId=vpc_id,
        TargetType="instance",
    )

    target_group_arn = target_group["TargetGroups"][0]["TargetGroupArn"]

    create_asg(
        autoscaling,
        settings.uploader,
        subnet_ids,
        target_group_arn,
    )

    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[settings.uploader.asg_name]
    )

    assert len(response["AutoScalingGroups"]) == 1


@mock_aws
def test_create_load_balancer():
    ec2 = boto3.client("ec2", region_name="us-east-2")
    elbv2 = boto3.client("elbv2", region_name="us-east-2")

    vpc_id = ec2.describe_vpcs()["Vpcs"][0]["VpcId"]
    subnets = ec2.describe_subnets()["Subnets"][:2]

    sg = ec2.create_security_group(
        GroupName="lab05-test-alb-sg",
        Description="Test ALB security group",
        VpcId=vpc_id,
    )["GroupId"]

    response = elbv2.create_load_balancer(
        Name="lab05-test-alb",
        Subnets=[s["SubnetId"] for s in subnets],
        SecurityGroups=[sg],
        Scheme="internet-facing",
        Type="application",
    )

    assert response["LoadBalancers"][0]["LoadBalancerArn"]


@mock_aws
def test_create_target_group():
    ec2 = boto3.client("ec2", region_name="us-east-2")
    elbv2 = boto3.client("elbv2", region_name="us-east-2")

    vpc_id = ec2.describe_vpcs()["Vpcs"][0]["VpcId"]

    response = elbv2.create_target_group(
        Name="lab05-test-tg",
        Protocol="HTTP",
        Port=3000,
        VpcId=vpc_id,
        TargetType="instance",
    )

    assert response["TargetGroups"][0]["Port"] == 3000


@mock_aws
def test_create_listener():
    ec2 = boto3.client("ec2", region_name="us-east-2")
    elbv2 = boto3.client("elbv2", region_name="us-east-2")

    vpc_id = ec2.describe_vpcs()["Vpcs"][0]["VpcId"]
    subnets = ec2.describe_subnets()["Subnets"][:2]

    sg = ec2.create_security_group(
        GroupName="lab05-listener-sg",
        Description="Test listener security group",
        VpcId=vpc_id,
    )["GroupId"]

    alb = elbv2.create_load_balancer(
        Name="lab05-listener-alb",
        Subnets=[s["SubnetId"] for s in subnets],
        SecurityGroups=[sg],
        Type="application",
    )["LoadBalancers"][0]

    tg = elbv2.create_target_group(
        Name="lab05-listener-tg",
        Protocol="HTTP",
        Port=3000,
        VpcId=vpc_id,
    )["TargetGroups"][0]

    listener = elbv2.create_listener(
        LoadBalancerArn=alb["LoadBalancerArn"],
        Protocol="HTTP",
        Port=8080,
        DefaultActions=[
            {
                "Type": "forward",
                "TargetGroupArn": tg["TargetGroupArn"],
            }
        ],
    )

    assert listener["Listeners"][0]["Port"] == 8080

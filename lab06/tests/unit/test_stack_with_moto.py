
"""Test Lab 06 AWS resources using Moto."""

import boto3
from moto import mock_aws

from stack.config import Settings
from stack.policies import weather_policy, advisor_policy
from stack.storage import (
    create_role,
    create_instance_profile,
    create_storage_and_iam,
)
from stack.compute import create_launch_template
from stack.network import get_network
from stack.scaling import create_asg
from stack.balancer import (
    create_target_group,
    create_listener,
)


REGION = "us-east-2"


@mock_aws
def test_weather_role():
    iam = boto3.client("iam", region_name=REGION)

    policy = weather_policy(
        REGION,
        "123456789012",
        "/itmo-444-544/db-password",
    )

    create_role(iam, "Lab06WeatherTestRole", policy)

    role = iam.get_role(RoleName="Lab06WeatherTestRole")
    assert role["Role"]["RoleName"] == "Lab06WeatherTestRole"

    attached = iam.get_role_policy(
        RoleName="Lab06WeatherTestRole",
        PolicyName="Lab06WeatherTestRole-policy",
    )

    assert attached["PolicyDocument"]["Statement"][0]["Action"] == [
        "ssm:GetParameter"
    ]


@mock_aws
def test_advisor_role():
    iam = boto3.client("iam", region_name=REGION)

    policy = advisor_policy(
        REGION,
        "123456789012",
        "/itmo-444-544/gemini-api-key",
    )

    create_role(iam, "Lab06AdvisorTestRole", policy)

    role = iam.get_role(RoleName="Lab06AdvisorTestRole")
    assert role["Role"]["RoleName"] == "Lab06AdvisorTestRole"


@mock_aws
def test_instance_profile():
    iam = boto3.client("iam", region_name=REGION)

    create_role(
        iam,
        "Lab06TestRole",
        weather_policy(
            REGION,
            "123456789012",
            "/itmo-444-544/db-password",
        ),
    )

    create_instance_profile(
        iam,
        "Lab06TestProfile",
        "Lab06TestRole",
    )

    profile = iam.get_instance_profile(
        InstanceProfileName="Lab06TestProfile"
    )["InstanceProfile"]

    assert profile["Roles"][0]["RoleName"] == "Lab06TestRole"


@mock_aws
def test_both_application_roles():
    settings = Settings.from_file(".env")

    class Clients:
        iam = boto3.client("iam", region_name=REGION)
        sts = boto3.client("sts", region_name=REGION)

    create_storage_and_iam(Clients(), settings)

    for tier in settings.tiers:
        role = Clients.iam.get_role(RoleName=tier.role_name)
        assert role["Role"]["RoleName"] == tier.role_name


@mock_aws
def test_get_network():
    settings = Settings.from_file(".env")
    ec2 = boto3.client("ec2", region_name=REGION)

    vpc_id, subnet_ids = get_network(ec2, settings)

    assert vpc_id.startswith("vpc-")
    assert len(subnet_ids) == 2


@mock_aws
def test_weather_launch_template():
    settings = Settings.from_file(".env")
    ec2 = boto3.client("ec2", region_name=REGION)

    environment = {
        "AWS_REGION": REGION,
        "PORT": "3000",
        "DB_HOST": "test-db.example.com",
    }

    template_id = create_launch_template(
        ec2,
        settings.weather,
        settings,
        environment,
    )

    result = ec2.describe_launch_templates(
        LaunchTemplateIds=[template_id]
    )

    assert len(result["LaunchTemplates"]) == 1


@mock_aws
def test_advisor_launch_template():
    settings = Settings.from_file(".env")
    ec2 = boto3.client("ec2", region_name=REGION)

    environment = {
        "AWS_REGION": REGION,
        "PORT": "3000",
        "WEATHER_URL": "http://example.com:8080",
    }

    template_id = create_launch_template(
        ec2,
        settings.advisor,
        settings,
        environment,
    )

    result = ec2.describe_launch_templates(
        LaunchTemplateIds=[template_id]
    )

    assert len(result["LaunchTemplates"]) == 1


@mock_aws
def test_weather_auto_scaling_group():
    settings = Settings.from_file(".env")

    ec2 = boto3.client("ec2", region_name=REGION)
    autoscaling = boto3.client("autoscaling", region_name=REGION)
    elbv2 = boto3.client("elbv2", region_name=REGION)

    ec2.create_launch_template(
        LaunchTemplateName=settings.weather.lt_name,
        LaunchTemplateData={
            "ImageId": settings.ami_id,
            "InstanceType": settings.instance_type,
        },
    )

    vpc_id, subnet_ids = get_network(ec2, settings)

    target_group_arn = create_target_group(
        elbv2,
        settings.weather,
        vpc_id,
        settings.app_port,
    )

    create_asg(
        autoscaling,
        settings.weather,
        subnet_ids,
        target_group_arn,
    )

    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[settings.weather.asg_name]
    )

    assert len(response["AutoScalingGroups"]) == 1


@mock_aws
def test_target_groups():
    settings = Settings.from_file(".env")

    ec2 = boto3.client("ec2", region_name=REGION)
    elbv2 = boto3.client("elbv2", region_name=REGION)

    vpc_id, _ = get_network(ec2, settings)

    for tier in settings.tiers:
        arn = create_target_group(
            elbv2,
            tier,
            vpc_id,
            settings.app_port,
        )

        assert arn.startswith("arn:aws:elasticloadbalancing:")


@mock_aws
def test_listener():
    settings = Settings.from_file(".env")

    ec2 = boto3.client("ec2", region_name=REGION)
    elbv2 = boto3.client("elbv2", region_name=REGION)

    vpc_id, subnet_ids = get_network(ec2, settings)

    sg_id = ec2.create_security_group(
        GroupName="lab06-test-alb-sg",
        Description="Lab 06 test ALB security group",
        VpcId=vpc_id,
    )["GroupId"]

    alb = elbv2.create_load_balancer(
        Name="lab06-test-alb",
        Subnets=subnet_ids,
        SecurityGroups=[sg_id],
        Scheme="internet-facing",
        Type="application",
    )["LoadBalancers"][0]

    target_group_arn = create_target_group(
        elbv2,
        settings.weather,
        vpc_id,
        settings.app_port,
    )

    listener_arn = create_listener(
        elbv2,
        alb["LoadBalancerArn"],
        settings.weather,
        target_group_arn,
    )

    assert listener_arn


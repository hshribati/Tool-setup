"""Check real AWS resources after deployment."""

import boto3
import pytest

from stack.config import Settings
from tests.helpers import deployed_stack


@pytest.mark.integration
def test_load_balancer_exists():
    outputs = deployed_stack()
    settings = Settings.from_file(".env")

    elbv2 = boto3.client("elbv2", region_name=settings.region)

    response = elbv2.describe_load_balancers(
        LoadBalancerArns=[outputs["alb_arn"]]
    )

    assert len(response["LoadBalancers"]) == 1


@pytest.mark.integration
def test_target_groups_exist():
    outputs = deployed_stack()
    settings = Settings.from_file(".env")

    elbv2 = boto3.client("elbv2", region_name=settings.region)

    response = elbv2.describe_target_groups(
        TargetGroupArns=[
            outputs["uploader_tg_arn"],
            outputs["viewer_tg_arn"],
        ]
    )

    assert len(response["TargetGroups"]) == 2


@pytest.mark.integration
def test_uploader_auto_scaling_group_exists():
    settings = Settings.from_file(".env")
    deployed_stack()

    autoscaling = boto3.client(
        "autoscaling", region_name=settings.region
    )

    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[settings.uploader.asg_name]
    )

    assert len(response["AutoScalingGroups"]) == 1


@pytest.mark.integration
def test_viewer_auto_scaling_group_exists():
    settings = Settings.from_file(".env")
    deployed_stack()

    autoscaling = boto3.client(
        "autoscaling", region_name=settings.region
    )

    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[settings.viewer.asg_name]
    )

    assert len(response["AutoScalingGroups"]) == 1


@pytest.mark.integration
def test_uploader_iam_role_exists():
    deployed_stack()
    settings = Settings.from_file(".env")

    iam = boto3.client("iam", region_name=settings.region)

    response = iam.get_role(
        RoleName=settings.uploader.role_name
    )

    assert response["Role"]["RoleName"] == settings.uploader.role_name


@pytest.mark.integration
def test_viewer_iam_role_exists():
    deployed_stack()
    settings = Settings.from_file(".env")

    iam = boto3.client("iam", region_name=settings.region)

    response = iam.get_role(
        RoleName=settings.viewer.role_name
    )

    assert response["Role"]["RoleName"] == settings.viewer.role_name


@pytest.mark.integration
def test_uploader_launch_template_exists():
    deployed_stack()
    settings = Settings.from_file(".env")

    ec2 = boto3.client("ec2", region_name=settings.region)

    response = ec2.describe_launch_templates(
        LaunchTemplateNames=[settings.uploader.lt_name]
    )

    assert len(response["LaunchTemplates"]) == 1


@pytest.mark.integration
def test_viewer_launch_template_exists():
    deployed_stack()
    settings = Settings.from_file(".env")

    ec2 = boto3.client("ec2", region_name=settings.region)

    response = ec2.describe_launch_templates(
        LaunchTemplateNames=[settings.viewer.lt_name]
    )

    assert len(response["LaunchTemplates"]) == 1

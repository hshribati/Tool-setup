
"""Check real Lab 06 AWS resources after deployment."""

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
            outputs["weather_tg_arn"],
            outputs["advisor_tg_arn"],
        ]
    )

    assert len(response["TargetGroups"]) == 2


@pytest.mark.integration
@pytest.mark.parametrize("tier_name", ["weather", "advisor"])
def test_auto_scaling_group_exists(tier_name):
    deployed_stack()
    settings = Settings.from_file(".env")

    tier = getattr(settings, tier_name)

    autoscaling = boto3.client(
        "autoscaling", region_name=settings.region
    )

    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[tier.asg_name]
    )

    assert len(response["AutoScalingGroups"]) == 1


@pytest.mark.integration
@pytest.mark.parametrize("tier_name", ["weather", "advisor"])
def test_iam_role_exists(tier_name):
    deployed_stack()
    settings = Settings.from_file(".env")

    tier = getattr(settings, tier_name)

    iam = boto3.client("iam", region_name=settings.region)

    response = iam.get_role(RoleName=tier.role_name)

    assert response["Role"]["RoleName"] == tier.role_name


@pytest.mark.integration
@pytest.mark.parametrize("tier_name", ["weather", "advisor"])
def test_launch_template_exists(tier_name):
    deployed_stack()
    settings = Settings.from_file(".env")

    tier = getattr(settings, tier_name)

    ec2 = boto3.client("ec2", region_name=settings.region)

    response = ec2.describe_launch_templates(
        LaunchTemplateNames=[tier.lt_name]
    )

    assert len(response["LaunchTemplates"]) == 1


@pytest.mark.integration
def test_postgresql_database_exists():
    deployed_stack()
    settings = Settings.from_file(".env")

    rds = boto3.client("rds", region_name=settings.region)

    response = rds.describe_db_instances(
        DBInstanceIdentifier=settings.db_instance_id
    )

    database = response["DBInstances"][0]

    assert database["DBInstanceIdentifier"] == settings.db_instance_id
    assert database["Engine"] == "postgres"
    assert database["StorageEncrypted"] is True
    assert database["PubliclyAccessible"] is False


@pytest.mark.integration
def test_database_password_parameter_exists():
    deployed_stack()
    settings = Settings.from_file(".env")

    ssm = boto3.client("ssm", region_name=settings.region)

    response = ssm.describe_parameters(
        ParameterFilters=[
            {
                "Key": "Name",
                "Option": "Equals",
                "Values": [settings.db_password_param],
            }
        ]
    )

    assert len(response["Parameters"]) == 1
    assert response["Parameters"][0]["Type"] == "SecureString"


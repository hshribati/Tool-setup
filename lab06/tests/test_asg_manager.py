from moto import mock_aws
from infrastructure.aws_client import (
    get_ec2_client,
    get_autoscaling_client
)
from infrastructure.asg_manager import create_auto_scaling_group


@mock_aws
def test_create_auto_scaling_group():
    ec2 = get_ec2_client()

    subnet_id = ec2.describe_subnets()["Subnets"][0]["SubnetId"]

    template = ec2.create_launch_template(
        LaunchTemplateName="lab05-test-template",
        LaunchTemplateData={
            "ImageId": "ami-12345678",
            "InstanceType": "t3.micro"
        }
    )

    template_id = template["LaunchTemplate"]["LaunchTemplateId"]

    result = create_auto_scaling_group(
        "lab05-test-asg",
        template_id,
        [subnet_id]
    )

    autoscaling = get_autoscaling_client()
    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=["lab05-test-asg"]
    )

    assert result == "lab05-test-asg"
    assert len(response["AutoScalingGroups"]) == 1
    assert response["AutoScalingGroups"][0]["DesiredCapacity"] == 1


@mock_aws
def test_delete_auto_scaling_group():
    from infrastructure.asg_manager import delete_auto_scaling_group

    ec2 = get_ec2_client()

    subnet_id = ec2.describe_subnets()["Subnets"][0]["SubnetId"]

    template = ec2.create_launch_template(
        LaunchTemplateName="lab05-delete-template",
        LaunchTemplateData={
            "ImageId": "ami-12345678",
            "InstanceType": "t3.micro"
        }
    )

    template_id = template["LaunchTemplate"]["LaunchTemplateId"]

    create_auto_scaling_group(
        "lab05-delete-asg",
        template_id,
        [subnet_id]
    )

    result = delete_auto_scaling_group("lab05-delete-asg")

    autoscaling = get_autoscaling_client()
    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=["lab05-delete-asg"]
    )

    assert result == "lab05-delete-asg"
    assert len(response["AutoScalingGroups"]) == 0

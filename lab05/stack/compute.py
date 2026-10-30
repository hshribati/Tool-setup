"""Create and delete EC2 launch templates."""

import json
from pathlib import Path

from stack.util import ignore_errors


def launch_template_data(tier, settings):
    """Load the existing launch-template settings."""
    path = Path(__file__).resolve().parent.parent / f"{tier.name}-launch-data.json"
    data = json.loads(path.read_text())

    data["ImageId"] = settings.ami_id
    data["InstanceType"] = settings.instance_type
    data["SecurityGroupIds"] = [settings.app_sg_id]
    data["IamInstanceProfile"] = {"Name": tier.profile_name}

    if settings.key_name:
        data["KeyName"] = settings.key_name

    return data


def create_launch_template(ec2, tier, settings):
    """Create a launch template or reuse it if it already exists."""
    data = launch_template_data(tier, settings)

    try:
        result = ec2.create_launch_template(
            LaunchTemplateName=tier.lt_name,
            LaunchTemplateData=data,
        )
        return result["LaunchTemplate"]["LaunchTemplateId"]

    except ec2.exceptions.ClientError as error:
        if error.response["Error"]["Code"] != "InvalidLaunchTemplateName.AlreadyExistsException":
            raise

        result = ec2.describe_launch_templates(
            LaunchTemplateNames=[tier.lt_name]
        )
        return result["LaunchTemplates"][0]["LaunchTemplateId"]


def delete_launch_template(ec2, tier):
    """Delete a launch template if it exists."""
    with ignore_errors("InvalidLaunchTemplateName.NotFoundException"):
        ec2.delete_launch_template(
            LaunchTemplateName=tier.lt_name
        )


"""Create, update, and delete EC2 launch templates."""

import base64

from botocore.exceptions import ClientError

from stack.user_data import build_user_data
from stack.util import ignore_errors


def launch_template_data(tier, settings, environment):
    """Build the EC2 launch template for one app."""

    script = build_user_data(tier, environment)

    data = {
        "ImageId": settings.ami_id,
        "InstanceType": settings.instance_type,
        "SecurityGroupIds": [settings.app_sg_id],
        "IamInstanceProfile": {
            "Name": tier.profile_name
        },
        "UserData": base64.b64encode(
            script.encode("utf-8")
        ).decode("ascii"),
        "MetadataOptions": {
            "HttpTokens": "required"
        },
    }

    if settings.key_name:
        data["KeyName"] = settings.key_name

    return data


def create_launch_template(ec2, tier, settings, environment):
    """Create a launch template or update an existing one."""

    data = launch_template_data(tier, settings, environment)

    try:
        result = ec2.create_launch_template(
            LaunchTemplateName=tier.lt_name,
            LaunchTemplateData=data,
        )

        return result["LaunchTemplate"]["LaunchTemplateId"]

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            != "InvalidLaunchTemplateName.AlreadyExistsException"
        ):
            raise

    # Find the existing launch template.
    result = ec2.describe_launch_templates(
        LaunchTemplateNames=[tier.lt_name]
    )

    template_id = result["LaunchTemplates"][0]["LaunchTemplateId"]

    # Create a new version with the latest application code.
    version = ec2.create_launch_template_version(
        LaunchTemplateId=template_id,
        LaunchTemplateData=data,
    )

    version_number = version["LaunchTemplateVersion"]["VersionNumber"]

    # Make the new version the default.
    ec2.modify_launch_template(
        LaunchTemplateId=template_id,
        DefaultVersion=str(version_number),
    )

    return template_id


def delete_launch_template(ec2, tier):
    """Delete a launch template if it exists."""

    with ignore_errors(
        "InvalidLaunchTemplateName.NotFoundException"
    ):
        ec2.delete_launch_template(
            LaunchTemplateName=tier.lt_name
        )


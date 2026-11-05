
"""AWS networking helpers for Lab 06."""

from botocore.exceptions import ClientError


ALB_DESCRIPTION = "Lab 06 Weather and Advisor ALB"


def get_network(ec2, settings):
    """Find the default VPC and two subnets."""

    vpcs = ec2.describe_vpcs(
        Filters=[
            {"Name": "isDefault", "Values": ["true"]}
        ]
    )["Vpcs"]

    if not vpcs:
        raise RuntimeError("No default VPC found.")

    vpc_id = vpcs[0]["VpcId"]

    subnets = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]}
        ]
    )["Subnets"]

    selected = []

    for az in (settings.az_a, settings.az_b):
        matches = [
            subnet["SubnetId"]
            for subnet in subnets
            if subnet["AvailabilityZone"] == az
        ]

        if not matches:
            raise RuntimeError(
                f"No subnet found in {az}"
            )

        selected.append(matches[0])

    return vpc_id, selected


def create_alb_security_group(ec2, settings, vpc_id):
    """Create or reuse the Lab 06 ALB security group."""

    groups = ec2.describe_security_groups(
        Filters=[
            {
                "Name": "group-name",
                "Values": [settings.alb_sg_name],
            },
            {
                "Name": "vpc-id",
                "Values": [vpc_id],
            },
        ]
    )["SecurityGroups"]

    if groups:
        group = groups[0]

        if group.get("Description") != ALB_DESCRIPTION:
            raise RuntimeError(
                "Existing ALB security group does not "
                "match Lab 06. Setup stopped."
            )

        sg_id = group["GroupId"]

    else:
        result = ec2.create_security_group(
            GroupName=settings.alb_sg_name,
            Description=ALB_DESCRIPTION,
            VpcId=vpc_id,
        )

        sg_id = result["GroupId"]

    for tier in settings.tiers:
        try:
            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": tier.listener_port,
                        "ToPort": tier.listener_port,
                        "IpRanges": [
                            {
                                "CidrIp": "0.0.0.0/0"
                            }
                        ],
                    }
                ],
            )

        except ClientError as error:
            if (
                error.response["Error"]["Code"]
                != "InvalidPermission.Duplicate"
            ):
                raise

    return sg_id


def allow_alb_to_apps(ec2, settings, alb_sg_id):
    """Allow ALB access to the applications on port 3000."""

    try:
        ec2.authorize_security_group_ingress(
            GroupId=settings.app_sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": settings.app_port,
                    "ToPort": settings.app_port,
                    "UserIdGroupPairs": [
                        {
                            "GroupId": alb_sg_id
                        }
                    ],
                }
            ],
        )

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            != "InvalidPermission.Duplicate"
        ):
            raise


def remove_alb_from_apps(ec2, settings, alb_sg_id):
    """Remove the ALB rule from the app security group."""

    if not alb_sg_id:
        return

    try:
        ec2.revoke_security_group_ingress(
            GroupId=settings.app_sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": settings.app_port,
                    "ToPort": settings.app_port,
                    "UserIdGroupPairs": [
                        {
                            "GroupId": alb_sg_id
                        }
                    ],
                }
            ],
        )

    except ClientError as error:
        if error.response["Error"]["Code"] not in (
            "InvalidPermission.NotFound",
            "InvalidGroup.NotFound",
        ):
            raise


def delete_alb_security_group(ec2, group_id):
    """Delete only the Lab 06 ALB security group."""

    if not group_id:
        return

    try:
        response = ec2.describe_security_groups(
            GroupIds=[group_id]
        )

    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "InvalidGroup.NotFound"
        ):
            print("ALB security group already deleted.")
            return

        raise

    group = response["SecurityGroups"][0]

    if group.get("Description") != ALB_DESCRIPTION:
        raise RuntimeError(
            "Security group does not match Lab 06. "
            "Deletion stopped for safety."
        )

    ec2.delete_security_group(
        GroupId=group_id
    )

    print("Lab 06 ALB security group deleted.")


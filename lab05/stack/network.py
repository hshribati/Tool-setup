"""AWS networking helpers for Lab 05."""

from stack.util import ignore_errors


def get_network(ec2, settings):
    """Find the VPC and two subnets from the configured AZs."""
    vpcs = ec2.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )["Vpcs"]

    if not vpcs:
        raise RuntimeError("No default VPC found")

    vpc_id = vpcs[0]["VpcId"]

    subnets = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["Subnets"]

    selected = []

    for az in (settings.az_a, settings.az_b):
        matches = [
            subnet["SubnetId"]
            for subnet in subnets
            if subnet["AvailabilityZone"] == az
        ]

        if not matches:
            raise RuntimeError(f"No subnet found in {az}")

        selected.append(matches[0])

    return vpc_id, selected


def create_alb_security_group(ec2, settings, vpc_id):
    """Create or find the ALB security group."""
    groups = ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [settings.alb_sg_name]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )["SecurityGroups"]

    if groups:
        return groups[0]["GroupId"]

    result = ec2.create_security_group(
        GroupName=settings.alb_sg_name,
        Description="Lab 05 Application Load Balancer",
        VpcId=vpc_id,
    )

    sg_id = result["GroupId"]

    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": port,
                "ToPort": port,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }
            for port in (
                settings.uploader.listener_port,
                settings.viewer.listener_port,
            )
        ],
    )

    return sg_id


def delete_alb_security_group(ec2, group_id):
    """Delete the ALB security group."""
    if not group_id:
        return

    with ignore_errors("InvalidGroup.NotFound"):
        ec2.delete_security_group(GroupId=group_id)

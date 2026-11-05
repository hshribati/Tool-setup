
"""Manage the Application Load Balancer and target groups."""

from botocore.exceptions import ClientError


def create_load_balancer(elbv2, settings, subnet_ids, security_group_id):
    """Create an internet-facing Application Load Balancer."""

    response = elbv2.create_load_balancer(
        Name=settings.alb_name,
        Subnets=subnet_ids,
        SecurityGroups=[security_group_id],
        Scheme="internet-facing",
        Type="application",
        IpAddressType="ipv4",
    )

    return response["LoadBalancers"][0]


def create_target_group(elbv2, tier, vpc_id, app_port=3000):
    """Create a target group for an application."""

    response = elbv2.create_target_group(
        Name=tier.tg_name,
        Protocol="HTTP",
        Port=app_port,
        VpcId=vpc_id,
        TargetType="instance",
        HealthCheckProtocol="HTTP",
        HealthCheckPath="/health",
        Matcher={"HttpCode": "200-399"},
    )

    return response["TargetGroups"][0]["TargetGroupArn"]


def create_listener(elbv2, load_balancer_arn, tier, target_group_arn):
    """Forward requests from the ALB to an application."""

    response = elbv2.create_listener(
        LoadBalancerArn=load_balancer_arn,
        Protocol="HTTP",
        Port=tier.listener_port,
        DefaultActions=[
            {
                "Type": "forward",
                "TargetGroupArn": target_group_arn,
            }
        ],
    )

    return response["Listeners"][0]["ListenerArn"]


def delete_load_balancer(elbv2, load_balancer_arn):
    """Delete the load balancer and wait for removal."""

    if not load_balancer_arn:
        return

    try:
        elbv2.delete_load_balancer(
            LoadBalancerArn=load_balancer_arn
        )

    except elbv2.exceptions.LoadBalancerNotFoundException:
        print("Load balancer already deleted.")
        return

    print("Waiting for load balancer deletion...")

    waiter = elbv2.get_waiter("load_balancers_deleted")

    waiter.wait(
        LoadBalancerArns=[load_balancer_arn],
        WaiterConfig={
            "Delay": 15,
            "MaxAttempts": 40,
        },
    )

    print("Load balancer deleted.")


def delete_target_group(elbv2, target_group_arn):
    """Delete a target group if it exists."""

    if not target_group_arn:
        return

    try:
        elbv2.delete_target_group(
            TargetGroupArn=target_group_arn
        )

    except elbv2.exceptions.TargetGroupNotFoundException:
        print("Target group already deleted.")


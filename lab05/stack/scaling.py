"""Manage Auto Scaling Groups for Lab 05."""

from stack.util import ignore_errors


def create_asg(autoscaling, tier, subnet_ids, target_group_arn):
    """Create an Auto Scaling Group for one application."""
    autoscaling.create_auto_scaling_group(
        AutoScalingGroupName=tier.asg_name,
        LaunchTemplate={
            "LaunchTemplateName": tier.lt_name,
            "Version": "$Latest",
        },
        MinSize=1,
        MaxSize=2,
        DesiredCapacity=1,
        VPCZoneIdentifier=",".join(subnet_ids),
        TargetGroupARNs=[target_group_arn],
        HealthCheckType="ELB",
        HealthCheckGracePeriod=300,
    )

    return tier.asg_name


def delete_asg(autoscaling, tier):
    """Delete an Auto Scaling Group if it exists."""
    from time import sleep

    with ignore_errors("ValidationError"):
        autoscaling.delete_auto_scaling_group(
            AutoScalingGroupName=tier.asg_name,
            ForceDelete=True,
        )

    for attempt in range(40):
        response = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[tier.asg_name]
        )

        if not response["AutoScalingGroups"]:
            print(f"Deleted Auto Scaling Group: {tier.asg_name}")
            return

        sleep(15)

    raise TimeoutError(
        f"Auto Scaling Group was not deleted: {tier.asg_name}"
    )

from infrastructure.aws_client import get_autoscaling_client


def create_auto_scaling_group(name, launch_template_id, subnet_ids):
    autoscaling = get_autoscaling_client()

    autoscaling.create_auto_scaling_group(
        AutoScalingGroupName=name,
        LaunchTemplate={
            "LaunchTemplateId": launch_template_id,
            "Version": "$Latest"
        },
        MinSize=1,
        MaxSize=2,
        DesiredCapacity=1,
        VPCZoneIdentifier=",".join(subnet_ids)
    )

    return name


def delete_auto_scaling_group(name):
    autoscaling = get_autoscaling_client()

    autoscaling.delete_auto_scaling_group(
        AutoScalingGroupName=name,
        ForceDelete=True
    )

    return name

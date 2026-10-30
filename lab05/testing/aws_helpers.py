import boto3

REGION = "us-east-2"

asg_client = boto3.client("autoscaling", region_name=REGION)


def get_instance_id(asg_name):
    response = asg_client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )

    groups = response["AutoScalingGroups"]

    if not groups:
        raise RuntimeError("Auto Scaling Group not found")

    instances = groups[0]["Instances"]

    if not instances:
        raise RuntimeError("No EC2 instance found")

    return instances[0]["InstanceId"]


def terminate_instance(instance_id):
    return asg_client.terminate_instance_in_auto_scaling_group(
        InstanceId=instance_id,
        ShouldDecrementDesiredCapacity=False
    )

from infrastructure.aws_client import get_ec2_client

def create_instance(image_id, instance_type="t3.micro"):
    ec2 = get_ec2_client()

    response = ec2.run_instances(
        ImageId=image_id,
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1
    )

    return response["Instances"][0]["InstanceId"]


def delete_instance(instance_id):
    ec2 = get_ec2_client()

    response = ec2.terminate_instances(
        InstanceIds=[instance_id]
    )

    return response["TerminatingInstances"][0]["InstanceId"]

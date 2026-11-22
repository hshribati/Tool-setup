from moto import mock_aws
from infrastructure.ec2_manager import create_instance
from infrastructure.aws_client import get_ec2_client

@mock_aws
def test_create_instance():
    instance_id = create_instance(
        image_id="ami-12345678"
    )

    ec2 = get_ec2_client()
    response = ec2.describe_instances(
        InstanceIds=[instance_id]
    )

    instance = response["Reservations"][0]["Instances"][0]

    assert instance_id.startswith("i-")
    assert instance["InstanceType"] == "t3.micro"


@mock_aws
def test_delete_instance():
    from infrastructure.ec2_manager import delete_instance

    instance_id = create_instance("ami-12345678")

    result = delete_instance(instance_id)

    ec2 = get_ec2_client()
    response = ec2.describe_instances(
        InstanceIds=[instance_id]
    )

    instance = response["Reservations"][0]["Instances"][0]

    assert result == instance_id
    assert instance["State"]["Name"] == "terminated"

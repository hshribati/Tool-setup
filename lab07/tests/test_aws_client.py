from moto import mock_aws
from infrastructure.aws_client import get_ec2_client, get_s3_client

@mock_aws
def test_ec2_client():
    client = get_ec2_client()
    assert client.meta.region_name == "us-east-2"

@mock_aws
def test_s3_client():
    client = get_s3_client()
    assert client.meta.region_name == "us-east-2"


@mock_aws
def test_load_balancer_client():
    from infrastructure.aws_client import get_elbv2_client

    client = get_elbv2_client()

    assert client.meta.region_name == "us-east-2"


@mock_aws
def test_autoscaling_client():
    from infrastructure.aws_client import get_autoscaling_client

    client = get_autoscaling_client()

    assert client.meta.region_name == "us-east-2"

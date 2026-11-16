from moto import mock_aws
from infrastructure.aws_client import get_ec2_client, get_elbv2_client
from infrastructure.alb_manager import create_load_balancer


@mock_aws
def test_create_load_balancer():
    ec2 = get_ec2_client()

    vpc = ec2.describe_vpcs()["Vpcs"][0]
    vpc_id = vpc["VpcId"]
    vpc_network = vpc["CidrBlock"].split(".")[:2]
    subnet_prefix = ".".join(vpc_network)

    subnet_ids = []
    for zone in ["us-east-2a", "us-east-2b"]:
        response = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock=f"{subnet_prefix}.100.0/24" if zone == "us-east-2a" else f"{subnet_prefix}.101.0/24",
            AvailabilityZone=zone
        )
        subnet_ids.append(response["Subnet"]["SubnetId"])

    sg = ec2.create_security_group(
        GroupName="lab05-test-alb-sg",
        Description="Test ALB security group",
        VpcId=vpc_id
    )

    arn = create_load_balancer(
        "lab05-test-alb",
        subnet_ids,
        [sg["GroupId"]]
    )

    elb = get_elbv2_client()
    response = elb.describe_load_balancers(
        LoadBalancerArns=[arn]
    )

    assert response["LoadBalancers"][0]["LoadBalancerName"] == "lab05-test-alb"


@mock_aws
def test_delete_load_balancer():
    from infrastructure.alb_manager import delete_load_balancer

    ec2 = get_ec2_client()
    vpc = ec2.describe_vpcs()["Vpcs"][0]
    vpc_id = vpc["VpcId"]
    subnet_prefix = ".".join(vpc["CidrBlock"].split(".")[:2])

    subnet_ids = []

    for zone, number in [("us-east-2a", 100), ("us-east-2b", 101)]:
        response = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock=f"{subnet_prefix}.{number}.0/24",
            AvailabilityZone=zone
        )
        subnet_ids.append(response["Subnet"]["SubnetId"])

    sg = ec2.create_security_group(
        GroupName="lab05-delete-alb-sg",
        Description="Test ALB deletion",
        VpcId=vpc_id
    )

    arn = create_load_balancer(
        "lab05-delete-alb",
        subnet_ids,
        [sg["GroupId"]]
    )

    result = delete_load_balancer(arn)

    elb = get_elbv2_client()
    response = elb.describe_load_balancers()

    assert result == arn
    assert all(
        lb["LoadBalancerArn"] != arn
        for lb in response["LoadBalancers"]
    )

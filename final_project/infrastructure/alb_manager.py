from infrastructure.aws_client import get_elbv2_client


def create_load_balancer(name, subnet_ids, security_group_ids):
    elb = get_elbv2_client()

    response = elb.create_load_balancer(
        Name=name,
        Subnets=subnet_ids,
        SecurityGroups=security_group_ids,
        Scheme="internet-facing",
        Type="application",
        IpAddressType="ipv4"
    )

    return response["LoadBalancers"][0]["LoadBalancerArn"]


def delete_load_balancer(load_balancer_arn):
    elb = get_elbv2_client()

    elb.delete_load_balancer(
        LoadBalancerArn=load_balancer_arn
    )

    return load_balancer_arn

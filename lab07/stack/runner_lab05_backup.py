"""Create and delete the Lab 05 AWS application stack."""

from stack.balancer import (
    create_listener,
    create_load_balancer,
    create_target_group,
    delete_load_balancer,
    delete_target_group,
)
from stack.compute import create_launch_template, delete_launch_template
from stack.network import (
    create_alb_security_group,
    delete_alb_security_group,
    get_network,
)
from stack.outputs import load_outputs, save_outputs
from stack.scaling import create_asg, delete_asg
from stack.storage import create_storage_and_iam, delete_storage_and_iam


def create_stack(clients, settings):
    """Create the uploader and viewer AWS resources."""

    create_storage_and_iam(clients, settings)

    vpc_id, subnet_ids = get_network(clients.ec2, settings)
    alb_sg_id = create_alb_security_group(
        clients.ec2, settings, vpc_id
    )

    alb = create_load_balancer(
        clients.elbv2, settings, subnet_ids, alb_sg_id
    )

    outputs = {
        "alb_arn": alb["LoadBalancerArn"],
        "alb_dns": alb["DNSName"],
        "alb_sg_id": alb_sg_id,
    }

    save_outputs(outputs)

    for tier in settings.tiers:
        create_launch_template(clients.ec2, tier, settings)

        tg_arn = create_target_group(
            clients.elbv2, tier, vpc_id, settings.app_port
        )

        outputs[f"{tier.name}_tg_arn"] = tg_arn
        save_outputs(outputs)

        create_listener(
            clients.elbv2,
            alb["LoadBalancerArn"],
            tier,
            tg_arn,
        )

        create_asg(
            clients.autoscaling, tier, subnet_ids, tg_arn
        )

        outputs[f"{tier.name}_tg_arn"] = tg_arn
        outputs[f"{tier.name}_url"] = (
            f"http://{alb['DNSName']}:{tier.listener_port}"
        )

    save_outputs(outputs)
    return outputs


def delete_stack(clients, settings):
    """Delete AWS resources in reverse order."""

    try:
        outputs = load_outputs()
    except FileNotFoundError:
        outputs = {}

    for tier in reversed(settings.tiers):
        delete_asg(clients.autoscaling, tier)

    alb_arn = outputs.get("alb_arn")

    if not alb_arn:
        try:
            response = clients.elbv2.describe_load_balancers(
                Names=[settings.alb_name]
            )
            alb_arn = response["LoadBalancers"][0]["LoadBalancerArn"]
        except clients.elbv2.exceptions.LoadBalancerNotFoundException:
            pass

    delete_load_balancer(clients.elbv2, alb_arn)

    for tier in reversed(settings.tiers):
        tg_arn = outputs.get(f"{tier.name}_tg_arn")

        if not tg_arn:
            response = clients.elbv2.describe_target_groups()
            for group in response["TargetGroups"]:
                if group["TargetGroupName"] == tier.tg_name:
                    tg_arn = group["TargetGroupArn"]
                    break

        delete_target_group(clients.elbv2, tg_arn)
        delete_launch_template(clients.ec2, tier)

    # Keep the existing ALB security group.
    # It was created manually before deployment.

    delete_storage_and_iam(clients, settings)

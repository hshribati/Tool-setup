
"""Create and delete the Final Weather Advisor AWS stack."""

import time

from stack.balancer import (
    create_listener,
    create_load_balancer,
    create_target_group,
    delete_load_balancer,
    delete_target_group,
)
from stack.database import delete_tables, ensure_table
from stack.notifications import delete_project_topics

from stack.compute import (
    create_launch_template,
    delete_launch_template,
)
from stack.network import (
    allow_alb_to_apps,
    create_alb_security_group,
    delete_alb_security_group,
    get_network,
    remove_alb_from_apps,
)
from stack.outputs import load_outputs, save_outputs
from stack.scaling import create_asg, delete_asg
from stack.storage import (
    create_storage_and_iam,
    delete_storage_and_iam,
)

WEATHER_TABLE = "final-weather-cache"

def create_stack(clients, settings):
    """Create the Weather and Advisor AWS resources."""

    print("Checking DynamoDB table...")

    ensure_table(clients.dynamodb, WEATHER_TABLE)

    print("DynamoDB table is available.")

    create_storage_and_iam(clients, settings)

    print("Waiting 60 seconds for AWS IAM permissions...")
    time.sleep(60)

    vpc_id, subnet_ids = get_network(
        clients.ec2, settings
    )

    alb_sg_id = create_alb_security_group(
        clients.ec2, settings, vpc_id
    )

    allow_alb_to_apps(
        clients.ec2, settings, alb_sg_id
    )

    alb = create_load_balancer(
        clients.elbv2,
        settings,
        subnet_ids,
        alb_sg_id,
    )

    outputs = {
        "alb_arn": alb["LoadBalancerArn"],
        "alb_dns": alb["DNSName"],
        "alb_sg_id": alb_sg_id,
    }

    save_outputs(outputs)

    for tier in settings.tiers:
        environment = {
            "AWS_REGION": settings.region,
            "PORT": str(settings.app_port),
        }

        if tier.name == "weather":
            environment.update({
                "WEATHER_TABLE": WEATHER_TABLE,
                "CACHE_SECONDS": str(
                    settings.cache_seconds
                ),
                "NWS_USER_AGENT": (
                    f"(ITMO 544 weather project, "
                    f"{settings.contact_email})"
                ),
            })

        elif tier.name == "advisor":
            environment.update({
                "WEATHER_URL": (
                    f"http://{alb['DNSName']}:"
                    f"{settings.weather.listener_port}"
                ),
                "GEMINI_KEY_PARAM": (
                    settings.gemini_param_name
                ),
                "GEMINI_MODEL": settings.gemini_model,
                "KEY_CACHE_SECONDS": str(
                    settings.key_cache_seconds
                ),
            })

        create_launch_template(
            clients.ec2,
            tier,
            settings,
            environment,
        )

        tg_arn = create_target_group(
            clients.elbv2,
            tier,
            vpc_id,
            settings.app_port,
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
            clients.autoscaling,
            tier,
            subnet_ids,
            tg_arn,
        )

        outputs[f"{tier.name}_url"] = (
            f"http://{alb['DNSName']}:"
            f"{tier.listener_port}"
        )

        save_outputs(outputs)

    return outputs


def delete_stack(clients, settings):
    """Delete AWS application resources in reverse order."""

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
            alb_arn = response["LoadBalancers"][0][
                "LoadBalancerArn"
            ]
        except clients.elbv2.exceptions.LoadBalancerNotFoundException:
            pass

    if alb_arn:
        delete_load_balancer(
            clients.elbv2, alb_arn
        )

    alb_sg_id = outputs.get("alb_sg_id")

    if not alb_sg_id:
        vpc_id, _ = get_network(
            clients.ec2, settings
        )

        groups = clients.ec2.describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": [settings.alb_sg_name],
                },
                {
                    "Name": "vpc-id",
                    "Values": [vpc_id],
                },
            ]
        )["SecurityGroups"]

        if groups:
            alb_sg_id = groups[0]["GroupId"]

    remove_alb_from_apps(
        clients.ec2,
        settings,
        alb_sg_id,
    )

    for tier in reversed(settings.tiers):
        tg_arn = outputs.get(
            f"{tier.name}_tg_arn"
        )

        if not tg_arn:
            response = (
                clients.elbv2.describe_target_groups()
            )

            for group in response["TargetGroups"]:
                if (
                    group["TargetGroupName"]
                    == tier.tg_name
                ):
                    tg_arn = group["TargetGroupArn"]
                    break

        if tg_arn:
            delete_target_group(
                clients.elbv2, tg_arn
            )

        delete_launch_template(
            clients.ec2, tier
        )

    if alb_sg_id:
        delete_alb_security_group(
            clients.ec2, alb_sg_id
        )

    delete_project_topics(clients.sns)

    delete_tables(clients.dynamodb, [WEATHER_TABLE])

    delete_storage_and_iam(
        clients, settings
    )


"""Create and delete the Lab 06 AWS application stack."""

from stack.balancer import (
    create_listener,
    create_load_balancer,
    create_target_group,
    delete_load_balancer,
    delete_target_group,
)
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


def get_database_host(clients, settings):
    """Wait until PostgreSQL is available."""

    print("Checking PostgreSQL database...")

    response = clients.rds.describe_db_instances(
        DBInstanceIdentifier=settings.db_instance_id
    )

    database = response["DBInstances"][0]
    status = database["DBInstanceStatus"]

    if status != "available":
        print("Database status:", status)
        print("Waiting for database to become available...")

        waiter = clients.rds.get_waiter(
            "db_instance_available"
        )

        waiter.wait(
            DBInstanceIdentifier=settings.db_instance_id,
            WaiterConfig={
                "Delay": 30,
                "MaxAttempts": 80,
            },
        )

        response = clients.rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )

        database = response["DBInstances"][0]

    endpoint = database.get("Endpoint", {})
    host = endpoint.get("Address")

    if not host:
        raise RuntimeError(
            "Database is available but has no endpoint."
        )

    print("PostgreSQL database is available.")
    return host


def create_stack(clients, settings):
    """Create the Weather and Advisor AWS resources."""

    # Check the database before creating application resources.
    db_host = get_database_host(clients, settings)

    create_storage_and_iam(clients, settings)

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
                "DB_HOST": db_host,
                "DB_PORT": "5432",
                "DB_NAME": settings.db_name,
                "DB_USER": settings.db_user,
                "DB_PASSWORD_PARAM": settings.db_password_param,
                "DB_CA_FILE": "/opt/app/rds-ca.pem",
                "CACHE_SECONDS": str(
                    settings.cache_seconds
                ),
                "NWS_USER_AGENT": (
                    f"(ITMO 544 weather lab, "
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

    # Delete both Auto Scaling Groups first.
    for tier in reversed(settings.tiers):
        delete_asg(clients.autoscaling, tier)

    # Find the load balancer.
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

    # Find the ALB security group.
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

    # Remove ALB access from application security group.
    remove_alb_from_apps(
        clients.ec2,
        settings,
        alb_sg_id,
    )

    # Delete target groups and launch templates.
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

    delete_storage_and_iam(
        clients, settings
    )


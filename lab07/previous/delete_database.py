
"""Safely delete Lab 06 PostgreSQL resources."""

import sys

import boto3
from botocore.exceptions import ClientError, WaiterError

from stack.config import Settings


PROJECT_TAG = "ITMO-544-Lab06"


def has_project_tag(tags):
    """Check whether a resource belongs to Lab 06."""
    return any(
        tag.get("Key") == "Project"
        and tag.get("Value") == PROJECT_TAG
        for tag in tags
    )


def get_database(rds, settings):
    """Find the Lab 06 database."""
    try:
        response = rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )
        return response["DBInstances"][0]

    except rds.exceptions.DBInstanceNotFoundFault:
        return None


def check_database_ownership(rds, database):
    """Check the database Project tag."""
    tags = rds.list_tags_for_resource(
        ResourceName=database["DBInstanceArn"]
    )["TagList"]

    if not has_project_tag(tags):
        raise RuntimeError(
            "Database does not have the Lab 06 Project tag. "
            "Deletion stopped."
        )


def check_subnet_group_ownership(rds, settings):
    """Check the subnet group before deletion."""
    try:
        response = rds.describe_db_subnet_groups(
            DBSubnetGroupName=settings.db_subnet_group_name
        )

    except rds.exceptions.DBSubnetGroupNotFoundFault:
        return None

    group = response["DBSubnetGroups"][0]

    if group.get("DBSubnetGroupDescription") != (
        "Lab 06 PostgreSQL subnets"
    ):
        raise RuntimeError(
            "Subnet group description does not match Lab 06."
        )

    tags = rds.list_tags_for_resource(
        ResourceName=group["DBSubnetGroupArn"]
    )["TagList"]

    if not has_project_tag(tags):
        raise RuntimeError(
            "Subnet group does not have the Lab 06 Project tag."
        )

    return group


def check_security_group_ownership(ec2, settings):
    """Check the database security group before deletion."""
    app_group = ec2.describe_security_groups(
        GroupIds=[settings.app_sg_id]
    )["SecurityGroups"][0]

    vpc_id = app_group["VpcId"]

    response = ec2.describe_security_groups(
        Filters=[
            {
                "Name": "group-name",
                "Values": [settings.db_sg_name],
            },
            {
                "Name": "vpc-id",
                "Values": [vpc_id],
            },
        ]
    )

    groups = response["SecurityGroups"]

    if not groups:
        return None

    group = groups[0]

    if group.get("Description") != (
        "Private PostgreSQL access for Lab 06"
    ):
        raise RuntimeError(
            "Security group description does not match Lab 06."
        )

    if not has_project_tag(group.get("Tags", [])):
        raise RuntimeError(
            "Security group does not have the Lab 06 Project tag."
        )

    return group


def check_password_ownership(ssm, settings):
    """Check the password parameter without reading its value."""
    response = ssm.describe_parameters(
        ParameterFilters=[
            {
                "Key": "Name",
                "Option": "Equals",
                "Values": [settings.db_password_param],
            }
        ]
    )

    parameters = response["Parameters"]

    if not parameters:
        return False

    parameter = parameters[0]

    if parameter.get("Name") != settings.db_password_param:
        raise RuntimeError(
            "Unexpected password parameter name."
        )

    if parameter.get("Description") != (
        "Lab 06 PostgreSQL password"
    ):
        raise RuntimeError(
            "Password parameter ownership could not be confirmed."
        )

    if parameter.get("Type") != "SecureString":
        raise RuntimeError(
            "Password parameter is not a SecureString."
        )

    return True


def delete_db_instance(rds, settings):
    """Delete the Lab 06 database."""
    database = get_database(rds, settings)

    if database is None:
        print("Database already deleted.")
        return

    check_database_ownership(rds, database)

    if database["DBInstanceStatus"] != "deleting":
        print("Deleting database:", settings.db_instance_id)

        rds.delete_db_instance(
            DBInstanceIdentifier=settings.db_instance_id,
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )
    else:
        print("Database deletion already started.")

    print("Waiting for database deletion...")

    waiter = rds.get_waiter("db_instance_deleted")

    waiter.wait(
        DBInstanceIdentifier=settings.db_instance_id,
        WaiterConfig={
            "Delay": 30,
            "MaxAttempts": 80,
        },
    )

    print("Database deleted.")


def delete_db_subnet_group(rds, settings):
    """Delete the verified Lab 06 subnet group."""
    group = check_subnet_group_ownership(rds, settings)

    if group is None:
        print("Database subnet group already deleted.")
        return

    rds.delete_db_subnet_group(
        DBSubnetGroupName=settings.db_subnet_group_name
    )

    print("Database subnet group deleted.")


def delete_db_security_group(ec2, settings):
    """Delete the verified Lab 06 security group."""
    group = check_security_group_ownership(ec2, settings)

    if group is None:
        print("Database security group already deleted.")
        return

    ec2.delete_security_group(
        GroupId=group["GroupId"]
    )

    print("Database security group deleted.")


def delete_db_password(ssm, settings):
    """Delete the verified Lab 06 password parameter."""
    if not check_password_ownership(ssm, settings):
        print("Database password parameter already deleted.")
        return

    ssm.delete_parameter(
        Name=settings.db_password_param
    )

    print("Database password parameter deleted.")


def check_remaining_backups(rds, settings):
    """Report snapshots without deleting them."""
    response = rds.describe_db_snapshots(
        Filters=[
            {
                "Name": "db-instance-id",
                "Values": [settings.db_instance_id],
            }
        ]
    )

    snapshots = response["DBSnapshots"]

    if snapshots:
        print("WARNING: Database snapshots still exist.")

        for snapshot in snapshots:
            print(
                "Snapshot:",
                snapshot["DBSnapshotIdentifier"],
            )
    else:
        print("No database snapshots found.")


def delete_database():
    """Clean up Lab 06 database resources."""
    settings = Settings.from_file()

    session = boto3.Session(
        region_name=settings.region
    )

    rds = session.client("rds")
    ec2 = session.client("ec2")
    ssm = session.client("ssm")

    print("Checking Lab 06 resource ownership...")

    # Check all existing resources before deleting anything.
    database = get_database(rds, settings)

    if database is not None:
        check_database_ownership(rds, database)

    check_subnet_group_ownership(rds, settings)
    check_security_group_ownership(ec2, settings)
    check_password_ownership(ssm, settings)

    print("Ownership checks passed.")
    print("Starting Lab 06 database cleanup...")

    delete_db_instance(rds, settings)
    delete_db_subnet_group(rds, settings)
    delete_db_security_group(ec2, settings)
    delete_db_password(ssm, settings)

    check_remaining_backups(rds, settings)

    print("Database cleanup completed.")
    print("Check AWS for remaining snapshots and backups.")


if __name__ == "__main__":
    try:
        delete_database()

    except (ClientError, WaiterError, RuntimeError) as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)


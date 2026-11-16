
"""Create the private PostgreSQL database for Lab 06."""

import secrets
import string
import sys

import boto3
from botocore.exceptions import ClientError

from stack.config import Settings


PROJECT_TAG = "ITMO-544-Lab06"


def has_project_tag(tags):
    """Check whether a resource belongs to Lab 06."""
    return any(
        tag.get("Key") == "Project"
        and tag.get("Value") == PROJECT_TAG
        for tag in tags
    )


def make_password():
    """Generate a strong database password."""
    alphabet = string.ascii_letters + string.digits + "!#%-_"
    return "".join(
        secrets.choice(alphabet) for _ in range(32)
    )


def get_or_create_password(ssm, parameter_name):
    """Reuse the Lab 06 password or create a new one."""
    try:
        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True,
        )

        parameter = response["Parameter"]

        if parameter.get("Type") != "SecureString":
            raise RuntimeError(
                "Existing password parameter is not a SecureString."
            )

        print("Reusing existing database password.")
        return parameter["Value"]

    except ClientError as error:
        if error.response["Error"]["Code"] != "ParameterNotFound":
            raise

    password = make_password()

    try:
        ssm.put_parameter(
            Name=parameter_name,
            Description="Lab 06 PostgreSQL password",
            Value=password,
            Type="SecureString",
            Overwrite=False,
        )

        print("New database password saved in SSM.")
        return password

    except ClientError as error:
        if error.response["Error"]["Code"] != "ParameterAlreadyExists":
            raise

        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True,
        )

        parameter = response["Parameter"]

        if parameter.get("Type") != "SecureString":
            raise RuntimeError(
                "Existing password parameter is not a SecureString."
            )

        print("Reusing existing database password.")
        return parameter["Value"]


def get_vpc_and_subnets(ec2, settings):
    """Find the VPC and subnets in two availability zones."""
    response = ec2.describe_security_groups(
        GroupIds=[settings.app_sg_id]
    )

    vpc_id = response["SecurityGroups"][0]["VpcId"]

    response = ec2.describe_subnets(
        Filters=[
            {
                "Name": "vpc-id",
                "Values": [vpc_id],
            },
            {
                "Name": "availability-zone",
                "Values": [settings.az_a, settings.az_b],
            },
        ]
    )

    chosen = {}

    for subnet in response["Subnets"]:
        az = subnet["AvailabilityZone"]
        chosen.setdefault(az, subnet["SubnetId"])

    if settings.az_a not in chosen or settings.az_b not in chosen:
        raise RuntimeError(
            "Could not find subnets in both availability zones."
        )

    return vpc_id, [
        chosen[settings.az_a],
        chosen[settings.az_b],
    ]


def create_db_security_group(ec2, settings, vpc_id):
    """Create or reuse the Lab 06 database security group."""
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

    if groups:
        group = groups[0]

        if group.get("Description") != (
            "Private PostgreSQL access for Lab 06"
        ):
            raise RuntimeError(
                "Existing security group has an unexpected description."
            )

        if not has_project_tag(group.get("Tags", [])):
            raise RuntimeError(
                "Existing security group does not have "
                "the Lab 06 project tag."
            )

        sg_id = group["GroupId"]
        print("Reusing Lab 06 database security group.")

    else:
        response = ec2.create_security_group(
            GroupName=settings.db_sg_name,
            Description="Private PostgreSQL access for Lab 06",
            VpcId=vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [
                        {
                            "Key": "Project",
                            "Value": PROJECT_TAG,
                        }
                    ],
                }
            ],
        )

        sg_id = response["GroupId"]
        print("Created Lab 06 database security group.")

    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 5432,
                    "ToPort": 5432,
                    "UserIdGroupPairs": [
                        {
                            "GroupId": settings.app_sg_id,
                        }
                    ],
                }
            ],
        )

    except ClientError as error:
        if error.response["Error"]["Code"] != (
            "InvalidPermission.Duplicate"
        ):
            raise

    return sg_id


def create_subnet_group(rds, settings, subnet_ids):
    """Create or reuse the Lab 06 database subnet group."""
    try:
        response = rds.describe_db_subnet_groups(
            DBSubnetGroupName=settings.db_subnet_group_name
        )

        group = response["DBSubnetGroups"][0]

        if group.get("DBSubnetGroupDescription") != (
            "Lab 06 PostgreSQL subnets"
        ):
            raise RuntimeError(
                "Existing subnet group has an unexpected description."
            )

        tags = rds.list_tags_for_resource(
            ResourceName=group["DBSubnetGroupArn"]
        )["TagList"]

        if not has_project_tag(tags):
            raise RuntimeError(
                "Existing subnet group does not have "
                "the Lab 06 project tag."
            )

        print("Reusing Lab 06 database subnet group.")

    except rds.exceptions.DBSubnetGroupNotFoundFault:
        rds.create_db_subnet_group(
            DBSubnetGroupName=settings.db_subnet_group_name,
            DBSubnetGroupDescription="Lab 06 PostgreSQL subnets",
            SubnetIds=subnet_ids,
            Tags=[
                {
                    "Key": "Project",
                    "Value": PROJECT_TAG,
                }
            ],
        )

        print("Created Lab 06 database subnet group.")


def create_database():
    """Create the private Lab 06 PostgreSQL database."""
    settings = Settings.from_file()

    session = boto3.Session(region_name=settings.region)

    ec2 = session.client("ec2")
    rds = session.client("rds")
    ssm = session.client("ssm")

    print("Checking AWS network...")

    vpc_id, subnet_ids = get_vpc_and_subnets(
        ec2,
        settings,
    )

    # Check for an existing database before changing resources.
    try:
        response = rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )

        existing = response["DBInstances"][0]

        tags = rds.list_tags_for_resource(
            ResourceName=existing["DBInstanceArn"]
        )["TagList"]

        if not has_project_tag(tags):
            raise RuntimeError(
                "Existing database does not have "
                "the Lab 06 project tag."
            )

        print(
            "Lab 06 database already exists:",
            existing["DBInstanceStatus"],
        )
        return

    except rds.exceptions.DBInstanceNotFoundFault:
        pass

    print("Creating database security group...")

    db_sg_id = create_db_security_group(
        ec2,
        settings,
        vpc_id,
    )

    print("Creating database subnet group...")

    create_subnet_group(
        rds,
        settings,
        subnet_ids,
    )

    print("Checking database password in SSM...")

    password = get_or_create_password(
        ssm,
        settings.db_password_param,
    )

    print("Creating private PostgreSQL database...")

    rds.create_db_instance(
        DBInstanceIdentifier=settings.db_instance_id,
        Engine="postgres",
        DBInstanceClass="db.t4g.micro",
        AllocatedStorage=20,
        StorageType="gp2",
        StorageEncrypted=True,
        MultiAZ=False,
        PubliclyAccessible=False,
        BackupRetentionPeriod=0,
        DBName=settings.db_name,
        MasterUsername=settings.db_user,
        MasterUserPassword=password,
        VpcSecurityGroupIds=[db_sg_id],
        DBSubnetGroupName=settings.db_subnet_group_name,
        AutoMinorVersionUpgrade=True,
        DeletionProtection=False,
        Tags=[
            {
                "Key": "Project",
                "Value": PROJECT_TAG,
            }
        ],
    )

    print("Database creation started.")
    print("Database ID:", settings.db_instance_id)
    print("The database may take several minutes to become available.")
    print("Password is stored in SSM and is not displayed.")


if __name__ == "__main__":
    try:
        create_database()

    except (ClientError, RuntimeError) as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)


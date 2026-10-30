"""Manage S3 storage and IAM roles."""

import json

from stack.policies import trust_policy, uploader_policy, viewer_policy
from stack.util import ignore_errors


def create_bucket(s3, bucket_name, region):
    """Create an S3 bucket if it does not already exist."""
    existing = s3.list_buckets().get("Buckets", [])

    if any(bucket["Name"] == bucket_name for bucket in existing):
        return bucket_name

    if region == "us-east-1":
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                "LocationConstraint": region
            },
        )

    return bucket_name


def create_role(iam, role_name, policy_document):
    """Create an EC2 role and attach its S3 permissions."""
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy(),
        )
    except iam.exceptions.EntityAlreadyExistsException:
        pass

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{role_name}-policy",
        PolicyDocument=policy_document,
    )

    return role_name


def create_instance_profile(iam, profile_name, role_name):
    """Create an instance profile and add the IAM role."""
    try:
        iam.create_instance_profile(
            InstanceProfileName=profile_name
        )
    except iam.exceptions.EntityAlreadyExistsException:
        pass

    profile = iam.get_instance_profile(
        InstanceProfileName=profile_name
    )["InstanceProfile"]

    existing_roles = [role["RoleName"] for role in profile["Roles"]]

    if role_name not in existing_roles:
        iam.add_role_to_instance_profile(
            InstanceProfileName=profile_name,
            RoleName=role_name,
        )

    return profile_name


def create_storage_and_iam(clients, settings):
    """Create the bucket, roles, and instance profiles."""
    create_bucket(
        clients.s3,
        settings.bucket_name,
        settings.region,
    )

    for tier in settings.tiers:
        policy = (
            uploader_policy(settings.bucket_name)
            if tier.name == "uploader"
            else viewer_policy(settings.bucket_name)
        )

        create_role(
            clients.iam,
            tier.role_name,
            policy,
        )

        create_instance_profile(
            clients.iam,
            tier.profile_name,
            tier.role_name,
        )


def delete_storage_and_iam(clients, settings):
    """Remove IAM resources and the S3 bucket."""
    for tier in reversed(settings.tiers):
        with ignore_errors("NoSuchEntity"):
            clients.iam.remove_role_from_instance_profile(
                InstanceProfileName=tier.profile_name,
                RoleName=tier.role_name,
            )

        with ignore_errors("NoSuchEntity"):
            clients.iam.delete_instance_profile(
                InstanceProfileName=tier.profile_name
            )

        with ignore_errors("NoSuchEntity"):
            clients.iam.delete_role_policy(
                RoleName=tier.role_name,
                PolicyName=f"{tier.role_name}-policy",
            )

        with ignore_errors("NoSuchEntity"):
            clients.iam.delete_role(
                RoleName=tier.role_name
            )

    with ignore_errors("NoSuchBucket"):
        # Remove objects before deleting the bucket.
        paginator = clients.s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=settings.bucket_name):
            objects = [
                {"Key": obj["Key"]}
                for obj in page.get("Contents", [])
            ]

            if objects:
                clients.s3.delete_objects(
                    Bucket=settings.bucket_name,
                    Delete={"Objects": objects},
                )

        clients.s3.delete_bucket(
            Bucket=settings.bucket_name
        )

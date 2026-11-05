
"""Manage IAM roles and instance profiles for Lab 06."""

from stack.policies import (
    trust_policy,
    weather_policy,
    advisor_policy,
)
from stack.util import ignore_errors


def create_role(iam, role_name, policy_document):
    """Create an EC2 role and attach its permissions."""
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
    """Create an instance profile and attach its IAM role."""
    try:
        iam.create_instance_profile(
            InstanceProfileName=profile_name
        )
    except iam.exceptions.EntityAlreadyExistsException:
        pass

    profile = iam.get_instance_profile(
        InstanceProfileName=profile_name
    )["InstanceProfile"]

    existing_roles = [
        role["RoleName"]
        for role in profile["Roles"]
    ]

    if role_name not in existing_roles:
        iam.add_role_to_instance_profile(
            InstanceProfileName=profile_name,
            RoleName=role_name,
        )

    return profile_name


def create_storage_and_iam(clients, settings):
    """Create IAM roles for Weather and Advisor."""

    account_id = clients.sts.get_caller_identity()["Account"]

    policies = {
        "weather": weather_policy(
            settings.region,
            account_id,
            settings.db_password_param,
        ),
        "advisor": advisor_policy(
            settings.region,
            account_id,
            settings.gemini_param_name,
        ),
    }

    for tier in settings.tiers:
        create_role(
            clients.iam,
            tier.role_name,
            policies[tier.name],
        )

        create_instance_profile(
            clients.iam,
            tier.profile_name,
            tier.role_name,
        )


def delete_storage_and_iam(clients, settings):
    """Delete Lab 06 IAM roles and instance profiles."""

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


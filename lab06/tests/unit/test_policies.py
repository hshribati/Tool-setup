
"""Unit tests for Lab 06 AWS IAM policies."""

import json

from stack.policies import (
    trust_policy,
    parameter_arn,
    weather_policy,
    advisor_policy,
)


def test_trust_policy():
    """Check that EC2 can use the IAM role."""

    policy = json.loads(trust_policy())
    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Principal"]["Service"] == "ec2.amazonaws.com"
    assert statement["Action"] == "sts:AssumeRole"


def test_parameter_arn():
    """Check that the SSM parameter ARN is correct."""

    arn = parameter_arn(
        "us-east-2",
        "123456789012",
        "/itmo-444-544/db-password",
    )

    assert arn == (
        "arn:aws:ssm:us-east-2:123456789012:"
        "parameter/itmo-444-544/db-password"
    )


def test_weather_policy():
    """Check that Weather can read only its database password."""

    policy = json.loads(
        weather_policy(
            "us-east-2",
            "123456789012",
            "/itmo-444-544/db-password",
        )
    )

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Action"] == ["ssm:GetParameter"]

    assert statement["Resource"] == (
        "arn:aws:ssm:us-east-2:123456789012:"
        "parameter/itmo-444-544/db-password"
    )


def test_advisor_policy():
    """Check that Advisor can read only its Gemini API key."""

    policy = json.loads(
        advisor_policy(
            "us-east-2",
            "123456789012",
            "/itmo-444-544/gemini-api-key",
        )
    )

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Action"] == ["ssm:GetParameter"]

    assert statement["Resource"] == (
        "arn:aws:ssm:us-east-2:123456789012:"
        "parameter/itmo-444-544/gemini-api-key"
    )


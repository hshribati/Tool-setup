
import json

from stack.policies import (
    trust_policy,
    parameter_arn,
    weather_policy,
    advisor_policy,
)


def test_trust_policy():
    policy = json.loads(trust_policy())

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Principal"]["Service"] == "ec2.amazonaws.com"
    assert statement["Action"] == "sts:AssumeRole"


def test_parameter_arn():
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
    """Check that Weather can access its DynamoDB cache."""

    policy = json.loads(
        weather_policy(
            "us-east-2",
            "123456789012",
            "final-weather-cache",
        )
    )

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"

    assert set(statement["Action"]) == {
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DescribeTable",
    }

    assert statement["Resource"] == (
        "arn:aws:dynamodb:us-east-2:123456789012:"
        "table/final-weather-cache"
    )


def test_advisor_policy():
    """Check that Advisor can read its Gemini API key."""

    policy = json.loads(
        advisor_policy(
            "us-east-2",
            "123456789012",
            "/itmo-444-544/gemini-api-key",
        )
    )

    statements = policy["Statement"]

    ssm_statement = next(
        s for s in statements
        if "ssm:GetParameter" in s["Action"]
    )

    assert ssm_statement["Effect"] == "Allow"

    assert ssm_statement["Resource"] == (
        "arn:aws:ssm:us-east-2:123456789012:"
        "parameter/itmo-444-544/gemini-api-key"
    )

    sns_statement = next(
        s for s in statements
        if "sns:Publish" in s["Action"]
    )

    assert sns_statement["Effect"] == "Allow"

    assert set(sns_statement["Action"]) == {
        "sns:CreateTopic",
        "sns:Subscribe",
        "sns:Publish",
        "sns:ListSubscriptionsByTopic",
        "sns:SetTopicAttributes",
    }

    assert sns_statement["Resource"] == (
        "arn:aws:sns:us-east-2:123456789012:"
        "final-weather-recipient-*"
    )

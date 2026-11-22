
"""IAM policies for the Final Weather Advisor project."""

import json


def trust_policy():
    """Allow EC2 instances to use an IAM role."""

    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
            }
        ],
    })


def parameter_arn(region, account_id, parameter_name):
    """Build the ARN of one SSM parameter."""

    name = parameter_name.lstrip("/")

    return (
        f"arn:aws:ssm:{region}:{account_id}:parameter/{name}"
    )


def weather_policy(region, account_id, table_name):
    """Allow Weather App to read and write DynamoDB data."""

    table_arn = (
        f"arn:aws:dynamodb:{region}:{account_id}:"
        f"table/{table_name}"
    )

    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DescribeTable",
                ],
                "Resource": table_arn,
            }
        ],
    })


def advisor_policy(region, account_id, gemini_param_name):
    """Allow Advisor to read Gemini key and use private SNS topics."""

    private_topic_arn = (
        f"arn:aws:sns:{region}:{account_id}:"
        "final-weather-recipient-*"
    )

    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": parameter_arn(
                    region,
                    account_id,
                    gemini_param_name,
                ),
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sns:CreateTopic",
                    "sns:Subscribe",
                    "sns:Publish",
                    "sns:ListSubscriptionsByTopic",
                    "sns:SetTopicAttributes",
                ],
                "Resource": private_topic_arn,
            },
        ],
    })

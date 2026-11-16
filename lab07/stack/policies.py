
"""IAM policies for the Lab 06 Weather and Advisor applications."""

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


def weather_policy(region, account_id, db_password_param):
    """Allow Weather App to read only the database password."""
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": parameter_arn(
                    region,
                    account_id,
                    db_password_param,
                ),
            }
        ],
    })


def advisor_policy(region, account_id, gemini_param_name):
    """Allow Advisor App to read only the Gemini API key."""
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
            }
        ],
    })


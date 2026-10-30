"""IAM policies for the uploader and viewer applications."""

import json


def trust_policy():
    """Allow EC2 instances to use an IAM role."""
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    })


def uploader_policy(bucket_name):
    """Allow uploading files to S3."""
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:PutObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            }
        ],
    })


def viewer_policy(bucket_name):
    """Allow reading files from S3."""
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            }
        ],
    })

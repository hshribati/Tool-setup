"""Unit tests for AWS IAM policies."""

import json

from stack.policies import (
    trust_policy,
    uploader_policy,
    viewer_policy,
)


def test_trust_policy():
    policy = json.loads(trust_policy())

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Principal"]["Service"] == "ec2.amazonaws.com"
    assert statement["Action"] == "sts:AssumeRole"


def test_uploader_policy():
    policy = json.loads(uploader_policy("test-bucket"))

    statement = policy["Statement"][0]

    assert statement["Action"] == ["s3:PutObject"]
    assert statement["Resource"] == "arn:aws:s3:::test-bucket/*"


def test_viewer_policy():
    policy = json.loads(viewer_policy("test-bucket"))

    statement = policy["Statement"][0]

    assert statement["Action"] == ["s3:GetObject"]
    assert statement["Resource"] == "arn:aws:s3:::test-bucket/*"

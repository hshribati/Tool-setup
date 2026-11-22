
"""Tests for DynamoDB table management."""

import boto3
from moto import mock_aws

from stack.database import ensure_table, ensure_tables, delete_tables


@mock_aws
def test_create_table():
    """Test creating a DynamoDB table."""
    db = boto3.client("dynamodb", region_name="us-east-2")

    ensure_table(db, "test-weather")

    response = db.describe_table(TableName="test-weather")

    assert response["Table"]["TableName"] == "test-weather"
    assert response["Table"]["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST"


@mock_aws
def test_create_twice():
    """Creating the same table twice should work."""
    db = boto3.client("dynamodb", region_name="us-east-2")

    ensure_table(db, "test-weather")
    ensure_table(db, "test-weather")

    tables = db.list_tables()["TableNames"]

    assert tables.count("test-weather") == 1


@mock_aws
def test_create_and_delete_tables():
    """Test creating and deleting three tables."""
    db = boto3.client("dynamodb", region_name="us-east-2")

    names = ["test-weather", "test-reports", "test-counters"]

    ensure_tables(db, names)

    assert len(db.list_tables()["TableNames"]) == 3

    delete_tables(db, names)

    assert db.list_tables()["TableNames"] == []


@mock_aws
def test_delete_missing_table():
    """Deleting a missing table should not fail."""
    db = boto3.client("dynamodb", region_name="us-east-2")

    delete_tables(db, ["missing-table"])

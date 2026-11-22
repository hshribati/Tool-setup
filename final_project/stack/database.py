
"""DynamoDB tables for the Final Weather Advisor project."""

from botocore.exceptions import ClientError


def ensure_table(dynamodb, table_name):
    """Create a table if it does not already exist."""

    try:
        dynamodb.describe_table(TableName=table_name)
        print(f"Table already exists: {table_name}")
    except dynamodb.exceptions.ResourceNotFoundException:
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    "AttributeName": "id",
                    "KeyType": "HASH",
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "id",
                    "AttributeType": "S",
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        dynamodb.get_waiter("table_exists").wait(
            TableName=table_name
        )
        print(f"Created table: {table_name}")

    ttl = dynamodb.describe_time_to_live(
        TableName=table_name
    )["TimeToLiveDescription"]

    if ttl.get("TimeToLiveStatus") == "DISABLED":
        dynamodb.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": "expires_at",
            },
        )

    return table_name


def ensure_tables(dynamodb, table_names):
    """Ensure every project table exists."""
    for table_name in table_names:
        ensure_table(dynamodb, table_name)


def delete_tables(dynamodb, table_names):
    """Delete project tables, including when some are missing."""
    for table_name in reversed(table_names):
        try:
            dynamodb.delete_table(TableName=table_name)
            dynamodb.get_waiter("table_not_exists").wait(
                TableName=table_name
            )
            print(f"Deleted table: {table_name}")
        except dynamodb.exceptions.ResourceNotFoundException:
            print(f"Already deleted: {table_name}")

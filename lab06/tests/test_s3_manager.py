from moto import mock_aws
from infrastructure.s3_manager import create_bucket
from infrastructure.aws_client import get_s3_client

@mock_aws
def test_create_bucket():
    bucket_name = "lab05-test-bucket"

    result = create_bucket(bucket_name)

    s3 = get_s3_client()
    response = s3.list_buckets()

    bucket_names = [
        bucket["Name"]
        for bucket in response["Buckets"]
    ]

    assert result == bucket_name
    assert bucket_name in bucket_names


@mock_aws
def test_delete_bucket():
    from infrastructure.s3_manager import delete_bucket

    bucket_name = "lab05-delete-test-bucket"

    create_bucket(bucket_name)
    result = delete_bucket(bucket_name)

    s3 = get_s3_client()
    response = s3.list_buckets()

    bucket_names = [
        bucket["Name"]
        for bucket in response["Buckets"]
    ]

    assert result == bucket_name
    assert bucket_name not in bucket_names

from infrastructure.aws_client import get_s3_client

def create_bucket(bucket_name):
    s3 = get_s3_client()

    s3.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={
            "LocationConstraint": "us-east-2"
        }
    )

    return bucket_name


def delete_bucket(bucket_name):
    s3 = get_s3_client()

    s3.delete_bucket(Bucket=bucket_name)

    return bucket_name

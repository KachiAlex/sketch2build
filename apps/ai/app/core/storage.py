import os
import boto3
from botocore.exceptions import ClientError

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "sketch2build")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "sketch2build")
S3_BUCKET = os.getenv("S3_BUCKET", "sketch2build")

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name="us-east-1",
        )
    return _s3_client


def fetch_file_bytes(key: str) -> bytes:
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=key)
        return response["Body"].read()
    except ClientError as exc:
        raise RuntimeError(f"Failed to fetch {key} from storage: {exc}") from exc

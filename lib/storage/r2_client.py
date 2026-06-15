"""
Cloudflare R2 client — agent-core-infra
Upload artifacts and generate time-limited signed download URLs.
"""
import os
import boto3
from botocore.config import Config

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "")
R2_BUCKET     = os.getenv("R2_BUCKET", "agent-artifacts")

_client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto",
    config=Config(signature_version="s3v4"),
)

def upload_artifact(key: str, data: bytes, content_type: str = "application/pdf") -> None:
    _client.put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)

def signed_url(key: str, expires_hours: int = 48) -> str:
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET, "Key": key},
        ExpiresIn=expires_hours * 3600,
    )

def upload_and_sign(key: str, data: bytes, expires_hours: int = 48,
                    content_type: str = "application/pdf") -> str:
    upload_artifact(key, data, content_type)
    return signed_url(key, expires_hours)

def delete_artifact(key: str) -> None:
    _client.delete_object(Bucket=R2_BUCKET, Key=key)

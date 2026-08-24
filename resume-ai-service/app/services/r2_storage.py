"""Read-only access to the R2 bucket holding meeting VTT transcripts."""
from __future__ import annotations

import boto3

from app.core.config import R2_ACCESS_KEY_ID, R2_BUCKET_NAME, R2_SECRET_ACCESS_KEY, R2_URL


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def list_r2_vtt_files() -> list[str]:
    """List every .vtt object key in the bucket."""
    s3 = get_s3_client()
    response = s3.list_objects_v2(Bucket=R2_BUCKET_NAME)
    return [item["Key"] for item in response.get("Contents", []) if item["Key"].endswith(".vtt")]


def get_r2_vtt_content(file_key: str) -> str:
    """Download the text content of a single .vtt object."""
    s3 = get_s3_client()
    response = s3.get_object(Bucket=R2_BUCKET_NAME, Key=file_key)
    return response["Body"].read().decode("utf-8")

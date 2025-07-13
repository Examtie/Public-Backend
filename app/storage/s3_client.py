import os
import uuid

from dotenv import load_dotenv
from fastapi import UploadFile, HTTPException
import boto3

# Load environment variables from the Backend directory (two levels up)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# === Configuration ===
S3_ENDPOINT = os.getenv("S3_ENDPOINT")  # e.g. http://minio:9766
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET") or os.getenv("STORAGE_BUCKET_NAME") or os.getenv("STORAGE_BUCKET_NAME", "examtie")
STORAGE_REGION = os.getenv("STORAGE_REGION", "us-east-1")
PUBLIC_STORAGE_URL = os.getenv("PUBLIC_STORAGE_URL")  # optional—frontend public proxy path

S3_CONFIGURED = bool(S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY and STORAGE_BUCKET)

# The boto3 client will be created lazily so that a temporary connectivity issue
# (or running outside Docker where `minio` DNS is unknown) doesn’t permanently
# disable the storage backend during module import.
_s3_client = None

def _get_client():
    """Create (or return existing) boto3 client. Raises on failure."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=STORAGE_REGION,
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )
    return _s3_client



async def upload_to_s3(file: UploadFile) -> str:
    """Upload an `UploadFile` to the configured MinIO/S3 bucket and return a public URL."""
    if not S3_CONFIGURED:
        raise HTTPException(status_code=500, detail="S3 storage is not configured")

    s3 = _get_client()

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided or filename is empty")

    try:
        await file.seek(0)  # make sure we read from the start
        object_key = f"{uuid.uuid4()}_{file.filename}"

        # Ensure bucket exists (do this lazily once)
        try:
            s3.head_bucket(Bucket=STORAGE_BUCKET)
        except Exception:
            try:
                s3.create_bucket(Bucket=STORAGE_BUCKET)
            except Exception:
                pass  # bucket likely already exists or we lack perms; proceed anyway

        s3.upload_fileobj(
            file.file,
            STORAGE_BUCKET,
            object_key,
            ExtraArgs={"ACL": "public-read"},
        )

        # Compose public URL – if PUBLIC_STORAGE_URL provided, use that, else fall back to direct endpoint
        if PUBLIC_STORAGE_URL:
            public_base = PUBLIC_STORAGE_URL.rstrip("/")
            return f"{public_base}/{STORAGE_BUCKET}/{object_key}"
        else:
            # Note: MinIO uses virtual-host or path-style; we default to path-style here
            endpoint = S3_ENDPOINT.rstrip("/")
            return f"{endpoint}/{STORAGE_BUCKET}/{object_key}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")

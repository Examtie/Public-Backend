import boto3
import os
import re
from dotenv import load_dotenv
import uuid
from fastapi import UploadFile, HTTPException

# Load environment variables from the Backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Check if R2 is configured
R2_CONFIGURED = bool(
    os.getenv("R2_ACCESS_KEY") and 
    os.getenv("R2_SECRET_KEY") and 
    os.getenv("R2_BUCKET_NAME") and
    os.getenv("R2_ENDPOINT_URL")
)

s3_endpoint = os.getenv("R2_ENDPOINT_URL")

if R2_CONFIGURED:
    s3_endpoint = os.getenv("R2_ENDPOINT_URL")
    account_id = os.getenv("R2_ACCOUNT_ID")
    
    try:
        r2 = boto3.client(
            "s3",
            region_name=os.getenv("R2_REGION", "auto"),
            endpoint_url=s3_endpoint,
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
        )
        BUCKET = os.getenv("R2_BUCKET_NAME")
        
        # Ensure bucket exists
        existing_buckets = r2.list_buckets().get("Buckets", [])
        if not any(b["Name"] == BUCKET for b in existing_buckets):
            try:
                r2.create_bucket(Bucket=BUCKET)
                print(f"Created bucket '{BUCKET}' in local S3 store")
            except Exception as create_exc:
                print(f"Failed to create bucket '{BUCKET}': {create_exc}")
        
        S3_ENDPOINT = s3_endpoint
        
        print(f"R2 Configuration initialized:")
        
    except Exception as e:
        print(f"Error initializing R2 client: {e}")
        r2 = None
        BUCKET = None
        PUBLIC_ENDPOINT = None
        S3_ENDPOINT = None
        R2_CONFIGURED = False
else:
    r2 = None
    BUCKET = None
    PUBLIC_ENDPOINT = None
    S3_ENDPOINT = None
    print("R2 not configured - missing required environment variables")

async def upload_to_r2(file: UploadFile) -> str:
    if not R2_CONFIGURED:
        raise HTTPException(status_code=500, detail="R2 storage is not configured.")
    
    if not r2 or not BUCKET:
        raise HTTPException(status_code=500, detail="R2 client is not properly initialized")
    
    # Validate file
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided or filename is empty")
    
    try:
        # Reset file pointer to beginning
        await file.seek(0)
        
        file_id = f"{uuid.uuid4()}_{file.filename}"
        
        # Upload file to R2
        r2.upload_fileobj(
            file.file,
            BUCKET,
            file_id,
            ExtraArgs={"ACL": "public-read"}  # Make file public
        )
        
        public_base = os.getenv("PUBLIC_STORAGE_URL")
        if public_base:
            public_base = public_base.rstrip("/")
            return f"{public_base}/{BUCKET}/{file_id}"
        # Fallback to original endpoint (may be internal)
        return f"{s3_endpoint}/{file_id}"
            
    except Exception as e:
        error_msg = str(e)
        
        # Provide more specific error messages for common R2 issues
        if "NoSuchBucket" in error_msg:
            raise HTTPException(status_code=500, detail=f"R2 bucket '{BUCKET}' does not exist")
        elif "AccessDenied" in error_msg:
            raise HTTPException(status_code=500, detail="R2 access denied. Please check your credentials and permissions")
        elif "SignatureDoesNotMatch" in error_msg:
            raise HTTPException(status_code=500, detail="R2 authentication failed. Please check your access key and secret key")
        elif "EndpointConnectionError" in error_msg:
            raise HTTPException(status_code=500, detail="Cannot connect to R2 endpoint. Please check your endpoint URL")
        else:
            raise HTTPException(status_code=500, detail=f"File upload failed: {error_msg}")

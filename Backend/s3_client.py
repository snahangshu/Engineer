import boto3
import os
from dotenv import load_dotenv

load_dotenv()


AWS_REGION = "ap-south-1"
AWS_BUCKET = "door2fy-engineer-files"

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

def upload_file_to_s3(file_obj, filename, folder):
    key = f"{folder}/{filename}"

    s3.upload_fileobj(
        file_obj,
        AWS_BUCKET,
        key,
        ExtraArgs={"ACL": "public-read"}  # remove this for private files
    )

    return f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"

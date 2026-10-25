import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
    config=Config(signature_version="s3v4"),
)

bucket = os.environ["R2_BUCKET_NAME"]

response = client.head_bucket(Bucket=bucket)
print("R2 connection OK:", response["ResponseMetadata"]["HTTPStatusCode"])
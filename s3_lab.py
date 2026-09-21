import boto3

s3 = boto3.client("s3")

bucket_name = "rayen-aws-boto3-lab-2026"

s3.put_object(
    Bucket=bucket_name,
    Key="test.txt",
    Body="Hello from Boto3!"
)

print("Object uploaded successfully!")
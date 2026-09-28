import boto3
from pathlib import Path

lambda_client = boto3.client("lambda")

sts = boto3.client("sts")
account = sts.get_caller_identity()["Account"]

role_arn = f"arn:aws:iam::{account}:role/LabRole"

name = "rayen-boto3-lab-function"

package_bytes = Path("lambda_function.zip").read_bytes()

response = lambda_client.create_function(
    FunctionName=name,
    Runtime="python3.13",
    Role=role_arn,
    Handler="lambda_function.lambda_handler",
    Code={"ZipFile": package_bytes},
)

print("Lambda created successfully!")
print("Function ARN:", response["FunctionArn"])
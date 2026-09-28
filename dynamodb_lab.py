import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.client("dynamodb")
table_name = "rayen-boto3-lab-table"

try:
    response = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST"
    )
    print("Table created successfully!")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print("Table already exists.")
    else:
        raise

dynamodb.put_item(
    TableName=table_name,
    Item={
        "id": {"S": "1"},
        "name": {"S": "Rayen"},
        "course": {"S": "AWS Boto3"}
    }
)
print("Item inserted successfully!")

response = dynamodb.get_item(
    TableName=table_name,
    Key={"id": {"S": "1"}}
)
print("Item retrieved:")
print(response["Item"])

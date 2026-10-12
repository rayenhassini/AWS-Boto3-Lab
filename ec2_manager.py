import re
import boto3
from botocore.exceptions import ClientError, BotoCoreError, WaiterError

# ================= CONFIGURATION =================

REGION = "us-east-1"
KEY_NAME = "vockey"
INSTANCE_TYPE = "t3.micro"

LAB_TAG_KEY = "CreatedBy"
LAB_TAG_VALUE = "boto3-lab"

AMI_PARAMETER = (
    "/aws/service/ami-amazon-linux-latest/"
    "al2023-ami-kernel-default-x86_64"
)

WAITER_CONFIG = {"Delay": 5, "MaxAttempts": 60}

ec2 = boto3.client("ec2", region_name=REGION)
ssm = boto3.client("ssm", region_name=REGION)


# ================= HELPERS =================

def get_latest_ami():
    response = ssm.get_parameter(Name=AMI_PARAMETER)
    return response["Parameter"]["Value"]


def get_all_instances():
    paginator = ec2.get_paginator("describe_instances")
    instances = []

    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            instances.extend(reservation["Instances"])

    return instances


def is_lab_instance(instance):
    tags = {
        tag["Key"]: tag["Value"]
        for tag in instance.get("Tags", [])
    }
    return tags.get(LAB_TAG_KEY) == LAB_TAG_VALUE


def get_instance_id():
    instance_id = input("Enter EC2 instance ID: ").strip()

    if not re.fullmatch(r"i-[0-9a-fA-F]+", instance_id):
        print("Invalid instance ID format.")
        return None

    return instance_id


def get_instance_by_id(instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])

    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            return instance

    return None


def get_lab_instance(instance_id):
    instance = get_instance_by_id(instance_id)

    if instance is None:
        print("Instance not found.")
        return None

    if instance["State"]["Name"] in ("terminated", "shutting-down"):
        print("Instance is terminated or shutting down.")
        return None

    if not is_lab_instance(instance):
        print("SAFETY BLOCK: This instance was not created by this lab.")
        print("No changes were made.")
        return None

    return instance


def print_instance(instance):
    tags = {
        tag["Key"]: tag["Value"]
        for tag in instance.get("Tags", [])
    }

    print("-" * 45)
    print(f"ID          : {instance['InstanceId']}")
    print(f"Name        : {tags.get('Name', 'Unnamed')}")
    print(f"Type        : {instance['InstanceType']}")
    print(f"State       : {instance['State']['Name']}")
    print(f"AMI         : {instance.get('ImageId', 'N/A')}")
    print(
        f"AZ          : "
        f"{instance.get('Placement', {}).get('AvailabilityZone', 'N/A')}"
    )
    print(f"Public IP   : {instance.get('PublicIpAddress', 'Not assigned')}")
    print(f"Private IP  : {instance.get('PrivateIpAddress', 'N/A')}")
    print(f"Key pair    : {instance.get('KeyName', 'N/A')}")
    print(f"Launch time : {instance.get('LaunchTime', 'N/A')}")
    print(f"Security groups: {[sg['GroupName'] for sg in instance.get('SecurityGroups', [])]}")
    print(f"Tags        : {tags}")
    print(f"Lab instance: {is_lab_instance(instance)}")
    print("-" * 45)


def wait_for_state(instance_ids, waiter_name):
    ec2.get_waiter(waiter_name).wait(
        InstanceIds=instance_ids,
        WaiterConfig=WAITER_CONFIG,
    )


# ================= 1. LIST =================

def list_instances():
    print("\n========== EC2 INSTANCES ==========")
    count = 0

    for instance in get_all_instances():
        if instance["State"]["Name"] == "terminated":
            continue

        print_instance(instance)
        count += 1

    print(f"Total non-terminated instances: {count}")


# ================= 2. LAUNCH =================

def launch_instance():
    name = input("Name tag for the instance: ").strip()

    if not name:
        print("Name cannot be empty.")
        return

    ami_id = get_latest_ami()
    print(f"Latest Amazon Linux 2023 AMI: {ami_id}")
    print(f"Type: {INSTANCE_TYPE} | Key pair: {KEY_NAME}")

    if input("Launch instance? Type YES: ").strip().upper() != "YES":
        print("Launch cancelled.")
        return

    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        KeyName=KEY_NAME,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": name},
                {"Key": LAB_TAG_KEY, "Value": LAB_TAG_VALUE},
            ],
        }],
    )

    instance_id = response["Instances"][0]["InstanceId"]
    print(f"Launched {instance_id}; waiting for running state...")

    try:
        wait_for_state([instance_id], "instance_running")
        print("Instance is running.")
        print_instance(get_instance_by_id(instance_id))
    except WaiterError as error:
        print(f"Waiter timeout/error: {error}")
        print("Check the instance in the AWS Console.")


# ================= 3, 4, 5. STATE ACTIONS =================

def change_instance_state(action):
    instance_id = get_instance_id()
    if not instance_id:
        return

    instance = get_lab_instance(instance_id)
    if instance is None:
        return

    state = instance["State"]["Name"]

    if action == "start":
        if state != "stopped":
            print(f"Cannot start: current state is {state}.")
            return
        waiter = "instance_running"

    elif action == "stop":
        if state != "running":
            print(f"Cannot stop: current state is {state}.")
            return
        waiter = "instance_stopped"

    else:
        if state != "running":
            print(f"Cannot reboot: current state is {state}.")
            return
        waiter = None

    if input(f"{action.capitalize()} {instance_id}? Type YES: ").strip().upper() != "YES":
        print("Action cancelled.")
        return

    if action == "start":
        ec2.start_instances(InstanceIds=[instance_id])
    elif action == "stop":
        ec2.stop_instances(InstanceIds=[instance_id])
    else:
        ec2.reboot_instances(InstanceIds=[instance_id])

    if waiter:
        wait_for_state([instance_id], waiter)

    print(f"Action '{action}' completed.")
    print_instance(get_instance_by_id(instance_id))


# ================= 6. DESCRIBE =================

def describe_instance():
    instance_id = get_instance_id()
    if not instance_id:
        return

    instance = get_instance_by_id(instance_id)
    if instance is None:
        print("Instance not found.")
        return

    print_instance(instance)


# ================= 7. ADD TAG =================

def add_tag():
    instance_id = get_instance_id()
    if not instance_id:
        return

    instance = get_lab_instance(instance_id)
    if instance is None:
        return

    key = input("Tag key: ").strip()
    value = input("Tag value: ").strip()

    if not key or not value:
        print("Tag key and value cannot be empty.")
        return

    if key.lower() in (LAB_TAG_KEY.lower(), "aws:"):
        print("This tag key is reserved for lab ownership or AWS.")
        return

    if key.lower().startswith("aws:"):
        print("AWS tag keys are reserved.")
        return

    if input(f"Add tag {key}={value}? Type YES: ").strip().upper() != "YES":
        print("Tag operation cancelled.")
        return

    ec2.create_tags(
        Resources=[instance_id],
        Tags=[{"Key": key, "Value": value}],
    )
    print("Tag added successfully.")


# ================= 8. TERMINATE ONE =================

def terminate_instance():
    instance_id = get_instance_id()
    if not instance_id:
        return

    instance = get_lab_instance(instance_id)
    if instance is None:
        return

    print("Instance selected for termination:")
    print_instance(instance)

    if input("Permanently terminate this instance? Type TERMINATE: ").strip().upper() != "TERMINATE":
        print("Termination cancelled.")
        return

    ec2.terminate_instances(InstanceIds=[instance_id])
    print("Termination requested. Waiting...")

    try:
        wait_for_state([instance_id], "instance_terminated")
        print("Instance terminated successfully.")
    except WaiterError as error:
        print(f"Waiter timeout/error: {error}")


# ================= 9. CLEANUP =================

def cleanup_instances():
    response = ec2.describe_instances(Filters=[
        {"Name": f"tag:{LAB_TAG_KEY}", "Values": [LAB_TAG_VALUE]},
        {
            "Name": "instance-state-name",
            "Values": ["pending", "running", "stopping", "stopped"],
        },
    ])

    instances = [
        instance
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
    ]

    if not instances:
        print("No lab-created instances to clean up.")
        return

    print("\nThese lab-created instances will be terminated:")
    for instance in instances:
        print(f"- {instance['InstanceId']} | {get_name(instance)} | {instance['State']['Name']}")

    if input("Type TERMINATE to confirm cleanup: ").strip().upper() != "TERMINATE":
        print("Cleanup cancelled.")
        return

    ids = [instance["InstanceId"] for instance in instances]
    ec2.terminate_instances(InstanceIds=ids)
    print("Waiting for all instances to terminate...")

    try:
        wait_for_state(ids, "instance_terminated")
        print(f"Terminated {len(ids)} lab-created instance(s).")
    except WaiterError as error:
        print(f"Waiter timeout/error: {error}")


def get_name(instance):
    for tag in instance.get("Tags", []):
        if tag["Key"] == "Name":
            return tag["Value"]
    return "Unnamed"


# ================= MAIN MENU =================

def main():
    actions = {
        "1": list_instances,
        "2": launch_instance,
        "3": lambda: change_instance_state("start"),
        "4": lambda: change_instance_state("stop"),
        "5": lambda: change_instance_state("reboot"),
        "6": describe_instance,
        "7": add_tag,
        "8": terminate_instance,
        "9": cleanup_instances,
    }

    while True:
        print("\n========== EC2 MANAGER ==========")
        print("1. List instances (read-only)")
        print("2. Launch instance (t3.micro)")
        print("3. Start lab-created instance")
        print("4. Stop lab-created instance")
        print("5. Reboot lab-created instance")
        print("6. Describe any instance (read-only)")
        print("7. Add tag to lab-created instance")
        print("8. Terminate one lab-created instance")
        print("9. CLEAN UP all lab-created instances")
        print("0. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "0":
            print("Goodbye!")
            break

        action = actions.get(choice)
        if action is None:
            print("Invalid option.")
            continue

        try:
            action()
        except WaiterError as error:
            print(f"Waiter timeout/error: {error}")
        except (ClientError, BotoCoreError) as error:
            print(f"AWS error: {error}")
        except KeyboardInterrupt:
            print("\nOperation interrupted; returning to menu.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted.")


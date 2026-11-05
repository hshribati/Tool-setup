import os
import time

import boto3
import pytest
import requests
from dotenv import load_dotenv

from stack.outputs import load_outputs

load_dotenv()


def website_works(url):
    try:
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


@pytest.mark.chaos
@pytest.mark.parametrize("tier", ["weather", "advisor"])
def test_application_recovery(tier):
    region = os.environ.get("AWS_REGION", "us-east-2")
    slo = int(os.environ.get("RECOVERY_SLO_SECONDS", "180"))

    asg_name = os.environ[
        f"{tier.upper()}_ASG_NAME"
    ]

    outputs = load_outputs()
    url = outputs[f"{tier}_url"] + "/health"

    autoscaling = boto3.client(
        "autoscaling", region_name=region
    )

    assert website_works(url), (
        f"{tier} website is not working before the test"
    )

    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )

    instances = response["AutoScalingGroups"][0]["Instances"]
    assert instances, f"No instances found for {tier}"

    victim = instances[0]["InstanceId"]

    print(f"\n{tier}: terminating {victim}")
 
    started = time.monotonic()

    autoscaling.terminate_instance_in_auto_scaling_group(
        InstanceId=victim,
        ShouldDecrementDesiredCapacity=False,
    )


    recovered_after = None

    while time.monotonic() - started < slo * 2:
        response = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )
        instances = response["AutoScalingGroups"][0]["Instances"]

        replacement_ready = any(
            instance["InstanceId"] != victim
            and instance["LifecycleState"] == "InService"
            and instance["HealthStatus"] == "Healthy"
            for instance in instances
        )

        if replacement_ready and website_works(url):
            recovered_after = time.monotonic() - started
            break

        time.sleep(2)

    print(
        f"{tier}: recovery time = {recovered_after} "
        f"seconds (SLO = {slo} seconds)"
    )

    assert recovered_after is not None, (
        "The application did not recover in time"
    )

    assert recovered_after <= slo, (
        f"{tier} recovery exceeded {slo} seconds"
    )

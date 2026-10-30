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
@pytest.mark.parametrize("tier", ["uploader", "viewer"])
def test_application_recovery(tier):
    region = os.environ.get("AWS_REGION", "us-east-2")
    slo = int(os.environ.get("RECOVERY_SLO_SECONDS", "180"))

    asg_name = os.environ[
        f"{tier.upper()}_ASG_NAME"
    ]

    outputs = load_outputs()
    url = outputs[f"{tier}_url"]

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
    started = time.monotonic()
    saw_outage = False
    recovered_after = None

    while time.monotonic() - started < slo * 2:
        if website_works(url):
            if saw_outage:
                recovered_after = time.monotonic() - started
                break
        else:
            saw_outage = True

        time.sleep(2)

    print(
        f"{tier}: recovery time = {recovered_after} "
        f"seconds (SLO = {slo} seconds)"
    )

    assert saw_outage, (
        "The website never went down during the test"
    )

    assert recovered_after is not None, (
        "The website did not recover in time"
    )

    assert recovered_after <= slo, (
        f"{tier} recovery exceeded {slo} seconds"
    )

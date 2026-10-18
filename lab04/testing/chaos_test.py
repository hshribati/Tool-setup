import argparse
import csv
import time
from datetime import datetime, timezone

import boto3
from aws_helpers import get_instance_id, terminate_instance
from http_probe import probe

REGION = "us-east-2"

parser = argparse.ArgumentParser()
parser.add_argument("--asg", required=True)
parser.add_argument("--url", required=True)
parser.add_argument("--slo", type=int, default=180)
parser.add_argument("--interval", type=int, default=5)
parser.add_argument("--timeout", type=int, default=600)
args = parser.parse_args()

autoscaling = boto3.client("autoscaling", region_name=REGION)
elbv2 = boto3.client("elbv2", region_name=REGION)

if args.interval <= 0 or args.timeout <= 0 or args.slo <= 0:
    parser.error("SLO, interval, and timeout must be positive")

# Find the Auto Scaling Group.
response = autoscaling.describe_auto_scaling_groups(
    AutoScalingGroupNames=[args.asg]
)

if not response["AutoScalingGroups"]:
    raise SystemExit("ERROR: Auto Scaling Group not found.")

group = response["AutoScalingGroups"][0]
target_group_arns = group["TargetGroupARNs"]

if not target_group_arns:
    raise SystemExit("ERROR: No target group attached.")

target_group_arn = target_group_arns[0]

# Check the application before starting.
baseline = probe(args.url)

if not baseline["success"]:
    raise SystemExit("ERROR: Application is not healthy.")

instance_id = get_instance_id(args.asg)

print("Auto Scaling Group:", args.asg)
print("Original instance:", instance_id)
print("Baseline HTTP status:", baseline["status"])
print("Recovery SLO:", args.slo, "seconds")

filename = (
    "recovery_"
    + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    + ".csv"
)

# Confirm the original instance is healthy in the target group.
initial_targets = elbv2.describe_target_health(
    TargetGroupArn=target_group_arn
)["TargetHealthDescriptions"]

original_healthy = any(
    target["Target"]["Id"] == instance_id
    and target["TargetHealth"]["State"] == "healthy"
    for target in initial_targets
)

if not original_healthy:
    raise SystemExit(
        "ERROR: Original instance is not healthy in the ALB."
    )

print("Terminating original instance...")

start = time.monotonic()

terminate_instance(instance_id)

rows = []
recovery_time = None
saw_failure = False

while time.monotonic() - start < args.timeout:
    result = probe(args.url)

    # Check Auto Scaling Group instances.
    group = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[args.asg]
    )["AutoScalingGroups"][0]

    healthy_replacements = [
        instance["InstanceId"]
        for instance in group["Instances"]
        if instance["InstanceId"] != instance_id
        and instance["LifecycleState"] == "InService"
        and instance["HealthStatus"] == "Healthy"
    ]

    # Check ALB target health.
    targets = elbv2.describe_target_health(
        TargetGroupArn=target_group_arn
    )["TargetHealthDescriptions"]

    healthy_target_ids = {
        target["Target"]["Id"]
        for target in targets
        if target["TargetHealth"]["State"] == "healthy"
    }

    ready_replacements = [
        replacement_id
        for replacement_id in healthy_replacements
        if replacement_id in healthy_target_ids
    ]

    replacement_ready = bool(ready_replacements)

    new_instance = (
        ready_replacements[0]
        if replacement_ready
        else "waiting"
    )

    if not result["success"]:
        saw_failure = True

    elapsed = round(time.monotonic() - start, 2)

    recovered = replacement_ready and result["success"]

    rows.append({
        "elapsed_seconds": elapsed,
        "http_status": result["status"],
        "success": result["success"],
        "response_time": result["response_time"],
        "replacement_instance": new_instance,
        "replacement_healthy": replacement_ready,
        "saw_http_failure": saw_failure
    })

    print(
        f"{elapsed}s | HTTP {result['status']} | "
        f"success={result['success']} | "
        f"replacement_healthy={replacement_ready}"
    )

    if recovered:
        recovery_time = elapsed
        break

    time.sleep(args.interval)

# Save all results.
with open(filename, "w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "elapsed_seconds",
            "http_status",
            "success",
            "response_time",
            "replacement_instance",
            "replacement_healthy",
            "saw_http_failure"
        ]
    )

    writer.writeheader()
    writer.writerows(rows)

print()
print("CSV saved:", filename)

if recovery_time is None:
    print("RESULT: FAIL - Recovery not confirmed.")
elif recovery_time <= args.slo:
    print(f"RESULT: PASS - Recovery time: {recovery_time}s")
else:
    print(f"RESULT: FAIL - Recovery time: {recovery_time}s")

print("SLO:", args.slo, "seconds")

if not saw_failure:
    print(
        "NOTE: No HTTP failure was observed. "
        "Recovery time measures replacement readiness."
    )

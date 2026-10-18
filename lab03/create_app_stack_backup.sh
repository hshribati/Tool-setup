#!/bin/bash
set -euo pipefail

export AWS_PAGER=""

echo "Launching Uploader instance..."

UPLOADER_ID=$(aws ec2 run-instances \
  --launch-template LaunchTemplateName=Lab03-Uploader-Template,Version='$Default' \
  --count 1 \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Launching Viewer instance..."

VIEWER_ID=$(aws ec2 run-instances \
  --launch-template LaunchTemplateName=Lab03-Viewer-Template,Version='$Default' \
  --count 1 \
  --query 'Instances[0].InstanceId' \
  --output text)

# Save IDs for the cleanup script
printf '%s\n' "$UPLOADER_ID" > uploader-instance-id.txt
printf '%s\n' "$VIEWER_ID" > viewer-instance-id.txt

echo "Waiting for both instances to start..."

aws ec2 wait instance-running \
  --instance-ids "$UPLOADER_ID" "$VIEWER_ID"

echo "Both instances are running!"
echo

aws ec2 describe-instances \
  --instance-ids "$UPLOADER_ID" "$VIEWER_ID" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]' \
  --output table

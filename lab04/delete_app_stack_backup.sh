#!/bin/bash
set -euo pipefail

export AWS_PAGER=""

echo "Starting Lab 03 cleanup..."

# Check that instance ID files exist
if [[ ! -s uploader-instance-id.txt || ! -s viewer-instance-id.txt ]]; then
    echo "Error: Instance ID files are missing."
    exit 1
fi

UPLOADER_ID=$(cat uploader-instance-id.txt)
VIEWER_ID=$(cat viewer-instance-id.txt)

echo "Terminating Uploader: $UPLOADER_ID"
echo "Terminating Viewer: $VIEWER_ID"

aws ec2 terminate-instances \
  --instance-ids "$UPLOADER_ID" "$VIEWER_ID" \
  --output table

echo "Waiting for both instances to terminate..."

aws ec2 wait instance-terminated \
  --instance-ids "$UPLOADER_ID" "$VIEWER_ID"

echo
echo "Both EC2 instances terminated successfully!"

aws ec2 describe-instances \
  --instance-ids "$UPLOADER_ID" "$VIEWER_ID" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name]' \
  --output table

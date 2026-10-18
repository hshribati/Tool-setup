#!/bin/bash
set -euo pipefail

export AWS_PAGER=""
cd /workspace/lab03

# Check for existing EC2 instances before creating new ones
for ID_FILE in uploader-instance-id.txt viewer-instance-id.txt; do
    if [[ -s "$ID_FILE" ]]; then
        INSTANCE_ID=$(cat "$ID_FILE")

        STATE=$(aws ec2 describe-instances \
            --instance-ids "$INSTANCE_ID" \
            --query 'Reservations[0].Instances[0].State.Name' \
            --output text)

        if [[ "$STATE" != "terminated" ]]; then
            echo "Error: Instance $INSTANCE_ID is still $STATE."
            echo "Run ./delete_app_stack.sh before creating new instances."
            exit 1
        fi
    fi
done

echo "Creating a new Uploader launch template version..."

NEW_VERSION=$(aws ec2 create-launch-template-version \
    --launch-template-name Lab03-Uploader-Template \
    --source-version '$Latest' \
    --version-description "Uploader updated version" \
    --launch-template-data file://uploader-launch-data.json \
    --query 'LaunchTemplateVersion.VersionNumber' \
    --output text)

echo "Created Uploader version: $NEW_VERSION"
echo

echo "Launching Uploader instance..."

UPLOADER_ID=$(aws ec2 run-instances \
    --launch-template "LaunchTemplateName=Lab03-Uploader-Template,Version=$NEW_VERSION" \
    --count 1 \
    --query 'Instances[0].InstanceId' \
    --output text)

# Save the Uploader ID immediately
printf '%s\n' "$UPLOADER_ID" > uploader-instance-id.txt

echo "Uploader instance: $UPLOADER_ID"
echo

echo "Launching Viewer instance..."

VIEWER_ID=$(aws ec2 run-instances \
    --launch-template "LaunchTemplateName=Lab03-Viewer-Template,Version=\$Default" \
    --count 1 \
    --query 'Instances[0].InstanceId' \
    --output text)

# Save the Viewer ID immediately
printf '%s\n' "$VIEWER_ID" > viewer-instance-id.txt

echo "Viewer instance: $VIEWER_ID"
echo

echo "Waiting for both instances to start..."

aws ec2 wait instance-running \
    --instance-ids "$UPLOADER_ID" "$VIEWER_ID"

echo
echo "Both instances are running!"
echo

aws ec2 describe-instances \
    --instance-ids "$UPLOADER_ID" "$VIEWER_ID" \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]' \
    --output table

echo
echo "Lab 03 stack created successfully!"

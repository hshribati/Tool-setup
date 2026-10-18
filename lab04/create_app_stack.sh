#!/bin/bash
set -euo pipefail

export AWS_PAGER=""
cd /workspace/lab04

# Load Lab 04 settings
set -a
source .env
set +a

echo "Starting Lab 04 stack..."

# Find existing AWS resources
UPLOADER_TG_ARN=$(aws elbv2 describe-target-groups \
    --names "$UPLOADER_TG_NAME" \
    --region "$AWS_REGION" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)

VIEWER_TG_ARN=$(aws elbv2 describe-target-groups \
    --names "$VIEWER_TG_NAME" \
    --region "$AWS_REGION" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
    --names "$ALB_NAME" \
    --region "$AWS_REGION" \
    --query 'LoadBalancers[0].DNSName' \
    --output text)

# Create Uploader Auto Scaling Group
echo "Checking Uploader Auto Scaling Group..."

if aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "$UPLOADER_ASG_NAME" \
    --region "$AWS_REGION" \
    --query 'AutoScalingGroups[0].AutoScalingGroupName' \
    --output text | grep -Fxq "$UPLOADER_ASG_NAME"; then
    echo "Uploader ASG already exists."
else
    aws autoscaling create-auto-scaling-group \
        --auto-scaling-group-name "$UPLOADER_ASG_NAME" \
        --launch-template "LaunchTemplateName=$UPLOADER_LT_NAME,Version=\$Latest" \
        --min-size 1 \
        --max-size 1 \
        --desired-capacity 1 \
        --vpc-zone-identifier "$SUBNET_A,$SUBNET_B" \
        --target-group-arns "$UPLOADER_TG_ARN" \
        --health-check-type ELB \
        --health-check-grace-period 120 \
        --region "$AWS_REGION"

    echo "Uploader ASG created."
fi

# Create Viewer Auto Scaling Group
echo "Checking Viewer Auto Scaling Group..."

if aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "$VIEWER_ASG_NAME" \
    --region "$AWS_REGION" \
    --query 'AutoScalingGroups[0].AutoScalingGroupName' \
    --output text | grep -Fxq "$VIEWER_ASG_NAME"; then
    echo "Viewer ASG already exists."
else
    aws autoscaling create-auto-scaling-group \
        --auto-scaling-group-name "$VIEWER_ASG_NAME" \
        --launch-template "LaunchTemplateName=$VIEWER_LT_NAME,Version=\$Latest" \
        --min-size 1 \
        --max-size 1 \
        --desired-capacity 1 \
        --vpc-zone-identifier "$SUBNET_A,$SUBNET_B" \
        --target-group-arns "$VIEWER_TG_ARN" \
        --health-check-type ELB \
        --health-check-grace-period 120 \
        --region "$AWS_REGION"

    echo "Viewer ASG created."
fi

# Save resource information
cat > stack_outputs.env <<EOF
ALB_DNS=$ALB_DNS
UPLOADER_TG_ARN=$UPLOADER_TG_ARN
VIEWER_TG_ARN=$VIEWER_TG_ARN
UPLOADER_ASG_NAME=$UPLOADER_ASG_NAME
VIEWER_ASG_NAME=$VIEWER_ASG_NAME
EOF

echo
echo "Lab 04 stack creation commands completed!"
echo "Uploader: http://$ALB_DNS:8080/"
echo "Viewer:   http://$ALB_DNS:8081/"
echo
echo "Note: Wait for target health checks before using the apps."

#!/bin/bash
set -euo pipefail

export AWS_PAGER=""
export AWS_DEFAULT_REGION="us-east-2"

UPLOADER_ASG="itmo-444-544-uploader-asg"
VIEWER_ASG="itmo-444-544-viewer-asg"
ALB_NAME="itmo-444-544-app-alb"
UPLOADER_TG="itmo-444-544-uploader-tg"
VIEWER_TG="itmo-444-544-viewer-tg"

echo "Starting Lab 04 cleanup..."

# Delete Auto Scaling Groups first.
for ASG in "$UPLOADER_ASG" "$VIEWER_ASG"; do
    if aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names "$ASG" \
        --query 'AutoScalingGroups[0].AutoScalingGroupName' \
        --output text | grep -Fxq "$ASG"; then

        echo "Deleting Auto Scaling Group: $ASG"

        aws autoscaling update-auto-scaling-group \
            --auto-scaling-group-name "$ASG" \
            --min-size 0 \
            --desired-capacity 0

        aws autoscaling delete-auto-scaling-group \
            --auto-scaling-group-name "$ASG" \
            --force-delete
    fi
done

echo "Waiting for Auto Scaling Groups to disappear..."

for ASG in "$UPLOADER_ASG" "$VIEWER_ASG"; do
    while aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names "$ASG" \
        --query 'AutoScalingGroups[0].AutoScalingGroupName' \
        --output text | grep -Fxq "$ASG"; do
        sleep 10
    done
done

echo "Auto Scaling Groups deleted."

# Find and delete the Load Balancer.
ALB_ARN=$(aws elbv2 describe-load-balancers \
    --names "$ALB_NAME" \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text 2>/dev/null || true)

if [[ -n "$ALB_ARN" && "$ALB_ARN" != "None" ]]; then
    echo "Deleting Load Balancer..."

    aws elbv2 delete-load-balancer \
        --load-balancer-arn "$ALB_ARN"

    aws elbv2 wait load-balancers-deleted \
        --load-balancer-arns "$ALB_ARN"

    echo "Load Balancer deleted."
fi

# Delete target groups.
for TG in "$UPLOADER_TG" "$VIEWER_TG"; do
    TG_ARN=$(aws elbv2 describe-target-groups \
        --names "$TG" \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text 2>/dev/null || true)

    if [[ -n "$TG_ARN" && "$TG_ARN" != "None" ]]; then
        echo "Deleting Target Group: $TG"

        aws elbv2 delete-target-group \
            --target-group-arn "$TG_ARN"
    fi
done

# Delete launch templates.
for LT in "Lab03-Uploader-Template" "Lab03-Viewer-Template"; do
    if aws ec2 describe-launch-templates \
        --launch-template-names "$LT" \
        --query 'LaunchTemplates[0].LaunchTemplateName' \
        --output text 2>/dev/null | grep -Fxq "$LT"; then

        echo "Deleting Launch Template: $LT"

        aws ec2 delete-launch-template \
            --launch-template-name "$LT" \
            --output text
    fi
done

echo
echo "Waiting for EC2 instances to finish terminating..."
sleep 30

echo "Security groups will be checked separately." 

echo "Lab 04 cleanup commands completed!"

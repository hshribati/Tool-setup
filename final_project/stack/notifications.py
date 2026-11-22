"""SNS cleanup for the Final Weather Advisor project."""

TOPIC_PREFIX = "final-weather-recipient-"


def delete_project_topics(sns):
    """Delete only Final Weather Advisor SNS topics."""

    paginator = sns.get_paginator("list_topics")
    deleted = 0

    for page in paginator.paginate():
        for topic in page.get("Topics", []):
            arn = topic["TopicArn"]
            topic_name = arn.rsplit(":", 1)[-1]

            if not topic_name.startswith(TOPIC_PREFIX):
                continue

            sns.delete_topic(TopicArn=arn)
            print(f"Deleted SNS topic: {topic_name}")
            deleted += 1

    print(f"SNS cleanup finished. Topics deleted: {deleted}")

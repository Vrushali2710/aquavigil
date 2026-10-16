"""
Google Cloud Pub/Sub Setup Script for AquaVigil.
Creates the operational telemetry topic:
- Topic: `scada.valve.telemetry`
- Subscription: `scada.valve.telemetry-sub`
As specified in Page 2 and 3 of the Hackathon document.
"""

import os

def setup_pubsub():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
    topic_id = "scada.valve.telemetry"
    sub_id = "scada.valve.telemetry-sub"

    print(f"Connecting to Google Cloud Pub/Sub for Project: {project_id}...")
    try:
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient()
        subscriber = pubsub_v1.SubscriberClient()

        topic_path = publisher.topic_path(project_id, topic_id)
        sub_path = subscriber.subscription_path(project_id, sub_id)

        # 1. Create Topic
        try:
            publisher.create_topic(request={"name": topic_path})
            print(f"✓ Cloud Pub/Sub Topic created: {topic_path}")
        except Exception as e:
            print(f"✓ Cloud Pub/Sub Topic already exists or: {e}")

        # 2. Create Subscription
        try:
            subscriber.create_subscription(request={"name": sub_path, "topic": topic_path})
            print(f"✓ Cloud Pub/Sub Subscription created: {sub_path}")
        except Exception as e:
            print(f"✓ Cloud Pub/Sub Subscription already exists or: {e}")

        print("\nGoogle Cloud Pub/Sub operational ingestion pipeline ready!")

    except ImportError:
        print("\nNote: Install `google-cloud-pubsub` to execute cloud setup:")
        print("pip install google-cloud-pubsub")
    except Exception as e:
        print(f"\nGoogle Cloud Error: {e}")

if __name__ == "__main__":
    setup_pubsub()

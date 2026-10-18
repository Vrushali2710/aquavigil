"""
Google Cloud BigQuery GIS Setup Script for AquaVigil.
Creates the BigQuery dataset and network topology tables:
- `aquavigil_dataset.water_network`
- `aquavigil_dataset.sewerage_network`
- `aquavigil_dataset.scada_valve_events`
As specified in Page 3 of the Hackathon document.
"""

import os
import json
from pathlib import Path

def setup_bigquery():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
    dataset_id = os.getenv("BIGQUERY_DATASET", "aquavigil_dataset")

    print(f"Connecting to Google Cloud BigQuery for Project: {project_id}...")
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project_id)

        # 1. Create Dataset
        dataset_ref = f"{project_id}.{dataset_id}"
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"✓ Dataset {dataset_ref} ready.")

        # 2. Create Tables with GEOGRAPHY schemas
        water_schema = [
            bigquery.SchemaField("pipe_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("valve_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("pipe_age_years", "INTEGER"),
            bigquery.SchemaField("material", "STRING"),
            bigquery.SchemaField("geometry", "GEOGRAPHY", mode="REQUIRED"),
        ]
        water_table_ref = f"{dataset_ref}.water_network"
        water_table = bigquery.Table(water_table_ref, schema=water_schema)
        client.create_table(water_table, exists_ok=True)
        print(f"✓ Table {water_table_ref} ready.")

        sewer_schema = [
            bigquery.SchemaField("sewer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("condition_rating", "FLOAT"),
            bigquery.SchemaField("material", "STRING"),
            bigquery.SchemaField("geometry", "GEOGRAPHY", mode="REQUIRED"),
        ]
        sewer_table_ref = f"{dataset_ref}.sewerage_network"
        sewer_table = bigquery.Table(sewer_table_ref, schema=sewer_schema)
        client.create_table(sewer_table, exists_ok=True)
        print(f"✓ Table {sewer_table_ref} ready.")

        municipal_schema = [
            bigquery.SchemaField("asset_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("asset_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("asset_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_portal", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("description", "STRING"),
            bigquery.SchemaField("geometry", "GEOGRAPHY", mode="REQUIRED"),
        ]
        municipal_table_ref = f"{dataset_ref}.municipal_infrastructure"
        municipal_table = bigquery.Table(municipal_table_ref, schema=municipal_schema)
        client.create_table(municipal_table, exists_ok=True)
        print(f"✓ Table {municipal_table_ref} ready.")

        scada_schema = [
            bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("valve_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        ]
        scada_table_ref = f"{dataset_ref}.scada_valve_events"
        scada_table = bigquery.Table(scada_table_ref, schema=scada_schema)
        client.create_table(scada_table, exists_ok=True)
        print(f"✓ Table {scada_table_ref} ready.")

        water_context_schema = [
            bigquery.SchemaField("site_code", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("site_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("parameter_code", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("parameter_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("value", "FLOAT"),
            bigquery.SchemaField("unit", "STRING"),
            bigquery.SchemaField("timestamp", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("api_url", "STRING"),
        ]
        usgs_table_ref = f"{dataset_ref}.usgs_water_observations"
        usgs_table = bigquery.Table(usgs_table_ref, schema=water_context_schema)
        client.create_table(usgs_table, exists_ok=True)
        print(f"✓ Table {usgs_table_ref} ready.")

        print("\nAll Google Cloud BigQuery GIS tables successfully initialized!")

    except ImportError:
        print("\nNote: Install `google-cloud-bigquery` to execute cloud setup:")
        print("pip install google-cloud-bigquery")
    except Exception as e:
        print(f"\nGoogle Cloud Error: {e}")

if __name__ == "__main__":
    setup_bigquery()

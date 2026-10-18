import os
from google.cloud import bigquery

project = 'project-468c1498-16f8-4b24-98a'
print('project=', project)
client = bigquery.Client(project=project)
rows = list(client.list_datasets(max_results=10))
print('datasets=', [d.dataset_id for d in rows])
print('auth_ok=1')

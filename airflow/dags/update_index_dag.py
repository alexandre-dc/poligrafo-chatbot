from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import requests

API_URL = os.getenv("API_URL", "http://backend:8000")
API_TOKEN = os.getenv("API_TOKEN")

HEADERS = {"x-api-token": API_TOKEN}

def call_update_data():
    response = requests.post(f"{API_URL}/update-data", headers=HEADERS)
    if response.status_code != 200:
        raise Exception(f"Failed to update data: {response.text}")
    print(response.json())

def call_reindex():
    response = requests.post(f"{API_URL}/reindex", headers=HEADERS)
    if response.status_code != 200:
        raise Exception(f"Failed to reindex: {response.text}")
    print(response.json())

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="poligrafo_update_index",
    default_args=default_args,
    description="Collect new articles and reindex FAISS",
    schedule_interval="@hourly",
    start_date=datetime.today() - timedelta(days=1),
    catchup=False,
    is_paused_upon_creation=False,  # 👈 this line
    tags=["poligrafo", "fact-checking"],
) as dag:

    update_data_task = PythonOperator(
        task_id="update_data",
        python_callable=call_update_data,
    )

    reindex_task = PythonOperator(
        task_id="reindex_documents",
        python_callable=call_reindex,
    )

    update_data_task >> reindex_task
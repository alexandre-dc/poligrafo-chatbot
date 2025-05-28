FROM python:3.11

WORKDIR /app
COPY ./airflow/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY ./airflow/ /app/

CMD ["python", "dags/update_index.py"]
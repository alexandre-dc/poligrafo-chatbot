FROM python:3.11-slim

WORKDIR /app
COPY ./frontend/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY ./frontend/ /app/

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
FROM python:3.11-slim

WORKDIR /app
COPY ./backend/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY ./backend/ /app/
COPY ./shared/ /app/shared/

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
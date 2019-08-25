FROM python:3-slim

WORKDIR /app
ADD data /app/data

COPY src /app/src
COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

CMD ["python", "src/main.py"]
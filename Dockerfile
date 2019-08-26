FROM python:3-slim

WORKDIR /app

COPY src /app/src
COPY requirements.txt /app/requirements.txt

RUN apt-get update
RUN apt-get install -y wget
RUN pip install -r requirements.txt

RUN adduser vladfedchenko --quiet
USER vladfedchenko:vladfedchenko

CMD ["python", "src/main.py"]
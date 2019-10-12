FROM python:3-slim

WORKDIR /app

COPY src /app
COPY requirements.txt /app/requirements.txt

RUN apt-get update
RUN apt-get install -y wget ffmpeg
RUN pip install -r requirements.txt

RUN adduser vladfedchenko --quiet

RUN chown -R vladfedchenko /app

USER vladfedchenko:vladfedchenko

ENV FLASK_APP reposter.py

CMD ["flask", "run", "--host=0.0.0.0"]
# CMD ["bash"]
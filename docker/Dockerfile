FROM vladfedchenko/reddigram-reposter-base:latest

WORKDIR /app

COPY src /app
COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

RUN chown -R vladfedchenko /app

USER vladfedchenko:vladfedchenko

ENV FLASK_APP reposter.py

CMD ["flask", "run", "--host=0.0.0.0"]
# CMD ["bash"]

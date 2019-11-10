FROM python:3.7-slim-stretch

RUN adduser --disabled-login --gecos '' gargbotuser

RUN mkdir -p /home/gargbotuser/app
WORKDIR /home/gargbotuser/app

# for psycopg2
# https://hub.docker.com/r/tedder42/python3-psycopg2/dockerfile/
RUN apt-get update && \
	apt-get install -y --fix-missing --no-install-recommends  && \
	libpq-dev gcc &&  \
	apt-get clean && rm -rf /tmp/* /var/tmp/* /var/lib/apt/lists/*

RUN python -m venv venv && venv/bin/pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN venv/bin/pip install -r requirements.txt && apt-get autoremove -y gcc

USER gargbotuser

COPY gargbot_3000 gargbot_3000

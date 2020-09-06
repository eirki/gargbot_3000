FROM python:3.7-slim

RUN adduser --disabled-login --gecos '' gargbotuser

RUN mkdir -p /home/gargbotuser/app
WORKDIR /home/gargbotuser/app

RUN apt-get -y update \
    && apt-get install -y --fix-missing --no-install-recommends \
    fontconfig \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv venv && venv/bin/pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN venv/bin/pip install -r requirements.txt

USER gargbotuser

COPY gargbot_3000 gargbot_3000
COPY sql sql

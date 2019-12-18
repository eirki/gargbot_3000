FROM python:3.7-slim

RUN adduser --disabled-login --gecos '' gargbotuser

RUN mkdir -p /home/gargbotuser/app
WORKDIR /home/gargbotuser/app

RUN python -m venv venv && venv/bin/pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN venv/bin/pip install -r requirements.txt

USER gargbotuser

COPY gargbot_3000 gargbot_3000
COPY schema schema

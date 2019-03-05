FROM python:3.7-alpine

RUN adduser -D gargbotuser

RUN mkdir -p /home/gargbotuser/app
WORKDIR /home/gargbotuser/app

RUN apk update

#https://blog.sneawo.com/blog/2017/09/07/how-to-install-pillow-psycopg-pylibmc-packages-in-pythonalpine-image/
# for psycopg2
RUN apk add --no-cache postgresql-dev
# for Pillow
RUN apk add --no-cache jpeg-dev zlib-dev

RUN apk add --no-cache libressl-dev musl-dev libffi-dev

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN apk add --no-cache --virtual .build-deps build-base linux-headers && \
	venv/bin/pip install -r requirements.txt && \
	apk del .build-deps libressl-dev musl-dev libffi-dev

USER gargbotuser

COPY gargbot_3000 gargbot_3000

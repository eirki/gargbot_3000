# build environment
FROM node:12.10.0-slim as build

RUN adduser --disabled-login --gecos '' gargbotuser
RUN mkdir -p /home/gargbotuser/app
WORKDIR /home/gargbotuser/app

RUN npm install -g parcel-bundler

COPY package*.json ./
RUN npm install --production

COPY ./src ./src
COPY ./.env ./.env
RUN parcel build --no-minify ./src/*.html

# production environment
FROM nginx:1.17

RUN adduser --disabled-login --gecos '' gargbotuser

COPY --from=build /home/gargbotuser/app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

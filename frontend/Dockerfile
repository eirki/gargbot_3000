# build environment
FROM node:12.10.0-alpine as build

WORKDIR /app
ENV PATH /app/node_modules/.bin:$PATH
COPY package.json /app/package.json
RUN npm install --silent
COPY . /app
RUN ls /app/node_modules/
RUN webpack

# production environment
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html

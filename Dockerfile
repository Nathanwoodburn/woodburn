FROM nginx:alpine
COPY . /usr/share/nginx/html
COPY img/favicon.png /usr/share/nginx/html
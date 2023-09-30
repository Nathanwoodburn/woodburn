FROM nginx:alpine
COPY . /usr/share/nginx/html
COPY ./assets/img/favicon.png /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/conf.d/default.conf
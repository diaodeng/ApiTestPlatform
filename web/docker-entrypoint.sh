#!/bin/sh

echo "Injecting runtime config..."
envsubst < /usr/share/nginx/html/config.template.js > /usr/share/nginx/html/config.js

exec nginx -g "daemon off;"

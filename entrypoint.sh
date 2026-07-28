#!/bin/bash
set -e

# Run Django migrations if the command is for the web admin
if [ "$1" = "gunicorn" ]; then
    echo "Running Django migrations..."
    cd WEB_ADMIN_DJANGO
    python manage.py migrate
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
    cd ..
fi

exec "$@"

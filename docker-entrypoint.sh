#!/bin/sh
# Apply migrations and collect static files before starting the server.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"

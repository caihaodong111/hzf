#!/bin/sh
set -eu

if [ "$#" -eq 0 ] || [ "${1:-}" = "web" ]; then
    if [ "$#" -gt 0 ]; then
        shift
    fi

    python manage.py migrate --noinput
    python manage.py collectstatic --noinput

    exec daphne -b 0.0.0.0 -p 8000 aquaculture.asgi:application "$@"
fi

exec "$@"

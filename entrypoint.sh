#!/bin/bash
set -e

# PostgreSQL tayyor bo'lishini kutish
echo "PostgreSQL ga ulanish tekshirilmoqda..."
python -c "
import socket, time, os
host = os.getenv('DB_HOST', 'localhost')
port = int(os.getenv('DB_PORT', '5432'))
for i in range(30):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print(f'PostgreSQL ({host}:{port}) tayyor!')
        break
    except (socket.error, OSError):
        print(f'Kutilmoqda... ({i+1}/30)')
        time.sleep(2)
else:
    print('PostgreSQL ga ulanib bo\\'lmadi!')
    exit(1)
"

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

#!/usr/bin/env bash
# Script de construcción para el despliegue (Render u otra plataforma tipo PaaS).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
# Siembra usuarios de prueba, parámetros regulados y un expediente de ejemplo.
python manage.py seed_demo

"""Copia de seguridad de la base de datos SQLite.

Crea una copia consistente (usando el mecanismo de backup de SQLite, válido
aunque la aplicación esté en uso) en la carpeta `backups/`, con la fecha y la
hora en el nombre. Conserva las últimas COPIAS_A_CONSERVAR y borra las más
antiguas.

Uso:
    python manage.py copia_seguridad
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

COPIAS_A_CONSERVAR = 30


class Command(BaseCommand):
    help = "Crea una copia de seguridad fechada de la base de datos SQLite."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if "sqlite" not in db["ENGINE"]:
            raise CommandError("Este comando solo sirve para bases de datos SQLite.")

        origen = Path(db["NAME"])
        if not origen.exists():
            raise CommandError(f"No se encuentra la base de datos en {origen}.")

        carpeta = Path(settings.BASE_DIR) / "backups"
        carpeta.mkdir(exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta / f"db_{marca}.sqlite3"

        # Copia consistente con la API de backup de SQLite.
        con_origen = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
        try:
            con_destino = sqlite3.connect(destino)
            try:
                con_origen.backup(con_destino)
            finally:
                con_destino.close()
        finally:
            con_origen.close()

        tam_kb = destino.stat().st_size / 1024
        self.stdout.write(self.style.SUCCESS(
            f"Copia creada: {destino.name} ({tam_kb:,.0f} KB) en {carpeta}"
        ))

        # Conservar solo las más recientes.
        copias = sorted(carpeta.glob("db_*.sqlite3"), reverse=True)
        for vieja in copias[COPIAS_A_CONSERVAR:]:
            vieja.unlink()
            self.stdout.write(f"Eliminada copia antigua: {vieja.name}")

        self.stdout.write(f"Total de copias guardadas: {min(len(copias), COPIAS_A_CONSERVAR)}")

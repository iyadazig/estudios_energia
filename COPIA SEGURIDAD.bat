@echo off
title Copia de seguridad - Estudios Energia GEYPE
echo Creando copia de seguridad de la base de datos...
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py copia_seguridad
echo.
echo Listo. Las copias estan en la carpeta "backups".
pause

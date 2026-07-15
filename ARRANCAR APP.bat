@echo off
title Estudios Energia GEYPE
echo Arrancando Estudios Energia GEYPE...
echo Cuando veas "Starting development server", abre http://127.0.0.1:8000 en el navegador.
echo (Esta ventana debe quedar abierta mientras uses la aplicacion)
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
pause

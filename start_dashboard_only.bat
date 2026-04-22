@echo off
cd /d %~dp0
start "Drone Threat API" cmd /k start_api.bat
start "Drone Threat Frontend" cmd /k start_frontend.bat

@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Сборка Docker-образа «Штурман 38» ===
if not exist docker_golos mkdir docker_golos
if exist "..\golos\engines.py" (copy /Y "..\golos\engines.py" docker_golos\engines.py >nul) else (echo [!] Не нашёл ..\golos\engines.py — голос Яндекса в образе работать не будет)
if not exist seed mkdir seed
if exist irkutsk_osm.json copy /Y irkutsk_osm.json seed\ >nul
if exist danger_spots.json copy /Y danger_spots.json seed\ >nul
if exist settings_local.json (copy /Y settings_local.json seed\ >nul & echo Ключи Яндекса и 2ГИС встроены в образ.) else (echo [!] Нет settings_local.json — образ будет без ключей)
docker build -t shturman38 . || (echo [!] Сборка не удалась. Запущен ли Docker Desktop? & pause & exit /b 1)
if not exist for_friends mkdir for_friends
echo Сохраняю образ в for_friends\shturman38.tar ...
docker save -o for_friends\shturman38.tar shturman38 || (pause & exit /b 1)
echo.
echo Готово! Отправьте друзьям всю папку for_friends.
pause

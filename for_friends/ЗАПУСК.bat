@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Штурман 38 — игра-навигатор ===
docker version >nul 2>&1 || (echo Docker не запущен. Установите и откройте Docker Desktop: https://www.docker.com/products/docker-desktop/ & pause & exit /b 1)
echo Загружаю игру в Docker (первый раз — около минуты)...
docker load -i shturman38.tar >nul || (echo [!] Не нашёл файл shturman38.tar рядом с этим файлом & pause & exit /b 1)
docker rm -f shturman38 >nul 2>&1
docker run -d --name shturman38 -p 8765:8765 --env-file keys.env -v shturman38-data:/data shturman38 >nul || (echo [!] Не удалось запустить. Возможно, порт 8765 занят. & pause & exit /b 1)
timeout /t 3 >nul
start http://localhost:8765/
echo Игра открыта в браузере: http://localhost:8765/
echo Чтобы остановить — запустите СТОП.bat
pause

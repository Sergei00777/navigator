# «Штурман 38» — игра-навигатор. Сборка: docker_build.bat (или docker build -t shturman38 .)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 PORT=8765 NO_BROWSER=1 \
    DATA_DIR=/data GOLOS_DIR=/app/golos

WORKDIR /app
# запасной бесплатный голос (Microsoft), если у друга нет ключа Яндекса
RUN pip install --no-cache-dir "edge-tts>=7.0"

COPY app.py navstory.py dgis.py school.py game.html admin.html index.html ./
COPY web ./web
COPY docker_golos/ ./golos/
COPY seed/ ./seed/

VOLUME ["/data"]
EXPOSE 8765
CMD ["python", "app.py"]

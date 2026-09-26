FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
RUN useradd --uid 10001 --create-home journal && mkdir /data && chown journal:journal /data
USER journal
ENV HOST=0.0.0.0 PORT=8765 DATA_DIR=/data
EXPOSE 8765
VOLUME /data
CMD ["python", "-m", "server.main"]

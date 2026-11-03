# 파이 receiver 이미지 (라즈베리파이 5 arm64, 노트북 amd64 모두 빌드 가능)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY receiver ./receiver

RUN useradd --system --no-create-home app
USER app

CMD ["python", "-m", "receiver"]

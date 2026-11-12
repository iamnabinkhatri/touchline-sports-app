FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY js ./js
COPY styles ./styles
COPY index.html styles.css ./

# TrueNAS host-path storage should be owned by UID/GID 568 (the Apps user).
RUN mkdir -p /data && chown 568:568 /data

USER 568:568
EXPOSE 4173

CMD ["python", "-m", "backend.server"]

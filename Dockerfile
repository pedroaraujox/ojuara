FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 ojuara \
    && useradd --uid 10001 --gid ojuara --create-home --shell /usr/sbin/nologin ojuara

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=ojuara:ojuara app ./app
COPY --chown=ojuara:ojuara scripts ./scripts
COPY --chown=ojuara:ojuara servidor_producao.py ./

USER 10001:10001

EXPOSE 5000

CMD ["python", "servidor_producao.py"]

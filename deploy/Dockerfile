FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 nexo && useradd --uid 10001 --gid nexo --no-create-home nexo \
    && mkdir -p /app/data && chown nexo:nexo /app/data
COPY --chown=nexo:nexo server.py accounts.py deployment.py ai_services.py logic.py demo.py reception.py ./
COPY --chown=nexo:nexo public ./public
COPY --chown=nexo:nexo scripts/create_admin.py ./scripts/create_admin.py
USER nexo
EXPOSE 8080
CMD ["python", "server.py"]

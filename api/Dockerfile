# Container for a FUTURE private Cloud Run deployment (not deployed; requires review first).
# Production auth: Cloud Run service identity via Application Default Credentials (EE_AUTH_MODE=adc).
# No key files are copied into the image.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EE_AUTH_MODE=adc
WORKDIR /srv/api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home appuser
USER appuser
# Pass CODE_REVISION at build/deploy time (git is not available inside the image).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
# uvicorn isn't in requirements.txt because production (Vercel) runs this
# app through Mangum, not an ASGI server — add it just for the container.
RUN pip install --no-cache-dir -r requirements.txt uvicorn==0.42.0

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# api/index.py is the FastAPI app (webhook handler) that Vercel/Mangum also
# wraps in production; it inserts the repo root onto sys.path itself so
# `handlers`/`mock_db` resolve regardless of module vs script invocation.
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8000"]

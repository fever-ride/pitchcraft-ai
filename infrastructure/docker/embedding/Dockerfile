FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir torch

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    sentence-transformers

COPY server.py .

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]

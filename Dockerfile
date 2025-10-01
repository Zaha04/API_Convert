FROM python:3.11-slim

# Dependențe sistem pentru Pillow (libjpeg, zlib etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libjpeg62-turbo-dev zlib1g-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# PORT e setat de platformă (Render/railway). Uvicorn îl citește din env.
ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

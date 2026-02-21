FROM python:3.11-slim

WORKDIR /app

# All dependencies are stdlib — no pip install needed
COPY app/ app/

CMD ["python", "app/sensor.py"]

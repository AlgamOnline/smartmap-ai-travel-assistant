FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Copy env ke container
COPY .env .env

CMD ["python", "-u", "app.py"]

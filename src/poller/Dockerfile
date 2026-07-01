FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY polling.py .
COPY api/ ./api/

EXPOSE 8080

CMD ["python", "polling.py"]
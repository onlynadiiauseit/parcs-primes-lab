FROM python:3.12-slim-bookworm
WORKDIR /parcs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "start.py"]

FROM python:3.9-slim

ENV REPO_OWNER="hpcc-systems"
ENV REPO_NAME="HPCC-Platform"
ENV TAG="community_9.6.30-rc1"
ENV GIT_TKN="x"

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY OS.py .

CMD ["python", "main.py"]

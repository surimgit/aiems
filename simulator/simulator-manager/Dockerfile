FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir pyyaml docker
COPY main.py .
COPY static/ static/
CMD ["python", "main.py"]

FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

COPY ems/ai/requirements-train.txt /tmp/requirements-train.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-train.txt \
    && python -m pip install --no-cache-dir runpod==1.7.9

COPY ems /app/ems

ENV PYTHONPATH=/app/ems/ai
ENV S305_AI_DATA_ROOT=/workspace/s305-ai-data
ENV S305_AI_OUTPUT_ROOT=/workspace/runs

CMD ["python", "-m", "ems.ai.runpod.handler"]

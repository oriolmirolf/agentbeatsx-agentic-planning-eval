FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY green_agent/ ./green_agent/
COPY purple_agent/ ./purple_agent/
COPY examples/ ./examples/

COPY green_agent/VAL/bin/Validate /usr/local/bin/Validate
RUN chmod +x /usr/local/bin/Validate

ENV PYTHONPATH=/app
ENV EXAMPLES_DIR=/app/examples
ENV VAL_PATH=/usr/local/bin/Validate

ENTRYPOINT ["python", "-m", "green_agent.a2a_server"]
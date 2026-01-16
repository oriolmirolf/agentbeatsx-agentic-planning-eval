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

RUN mkdir -p /opt/val
COPY green_agent/VAL/bin/ /opt/val/

RUN ln -sf /opt/val/Validate /usr/local/bin/Validate && \
    chmod +x /opt/val/Validate

ENV PYTHONPATH=/app
ENV EXAMPLES_DIR=/app/examples
ENV VAL_PATH=/usr/local/bin/Validate 
ENV LD_LIBRARY_PATH=/opt/val:$LD_LIBRARY_PATH

LABEL org.opencontainers.image.source=https://github.com/oriolmirolf/agentbeatsx-agentic-planning-eval

ENTRYPOINT ["python", "-m", "green_agent.a2a_server"]
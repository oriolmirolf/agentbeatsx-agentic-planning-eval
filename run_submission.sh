#!/bin/bash
set -e

DOCKER_COMPOSE="/usr/local/bin/docker-compose"

echo ">>> Verifying Docker Compose..."
$DOCKER_COMPOSE version

echo ">>> Stopping old containers (Cleaning slate)..."
$DOCKER_COMPOSE down --remove-orphans

echo ">>> Building Docker Images..."
$DOCKER_COMPOSE build 

echo ">>> Starting Agents..."
$DOCKER_COMPOSE up -d

echo ">>> Waiting for agents to initialize (5s)..."
sleep 5

echo ">>> Copying trigger script to container..."
# Copy to 'green-agent' (hyphen)
docker cp trigger.py green-agent:/app/trigger.py

echo ">>> Triggering the Green Agent (via Python SDK)..."
docker exec green-agent python /app/trigger.py

echo -e "\n\n>>> 🟢 SUCCESS! Logs are streaming below (Ctrl+C to exit logs, agents keep running)..."
$DOCKER_COMPOSE logs -f green-agent
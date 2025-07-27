#!/bin/bash

# Variables
HOST="127.0.0.1"
PORT="8000"
APP_MODULE="app:app"
RELOAD="--reload"  

# Run the server
echo "Starting FastAPI server at http://$HOST:$PORT"
uvicorn $APP_MODULE --host $HOST --port $PORT $RELOAD

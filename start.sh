#!/bin/sh
set -e
cd backend
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $PORT

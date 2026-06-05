#!/bin/bash
set -e

echo "=== 指标调度系统 ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "Error: Docker Desktop is required"
    exit 1
fi

echo "Watching directory: /Users/ryan/Library/Application Support/yidongbangong/15902981622/filerecv"
echo ""

echo "Starting all services..."
docker compose up -d --build

echo ""
echo "System is running!"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  Watching: /Users/ryan/Library/Application Support/yidongbangong/15902981622/filerecv"
echo ""
echo "Put xlsx/csv/json files into the watched directory and they will be auto-parsed."
echo "Run 'docker compose logs -f' to see real-time logs."

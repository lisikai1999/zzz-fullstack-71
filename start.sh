#!/bin/bash
# Start both backend and frontend dev servers

cd "$(dirname "$0")"

echo "Starting backend..."
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "Starting frontend..."
cd ../frontend
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait

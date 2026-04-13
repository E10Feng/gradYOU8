---
name: restart
description: Kill and restart the backend (FastAPI/uvicorn on port 8001) and frontend (Vite on port 5173) dev servers. Use when the user says "restart", "reboot servers", or asks to restart the dev environment.
---

Restart the backend and frontend development servers for gradYOU8.

## Steps

1. Kill any existing processes on ports 8001 (backend) and 5173 (frontend):
   ```
   lsof -ti:8001 | xargs kill -9 2>/dev/null
   lsof -ti:5173 | xargs kill -9 2>/dev/null
   ```

2. **Verify the Vite proxy target matches the backend port.** Check `frontend/vite.config.ts` — the proxy entries for `/api` and `/chat` MUST point to `http://localhost:8001`. If they don't, fix them before starting the frontend.

3. Start the backend (from `backend/` directory):
   ```
   cd /Users/e10/gradYOU8/backend && nohup python3 -m uvicorn main:app --port 8001 --reload > /tmp/backend.log 2>&1 &
   ```

4. Start the frontend (from `frontend/` directory):
   ```
   cd /Users/e10/gradYOU8/frontend && nohup npm run dev > /tmp/frontend.log 2>&1 &
   ```

5. Verify the backend is healthy:
   ```
   curl -s --max-time 5 http://localhost:8001/api/health
   ```

6. Verify the frontend is serving:
   ```
   curl -s --max-time 3 http://localhost:5173 | head -1
   ```

7. If either fails, check logs at `/tmp/backend.log` or `/tmp/frontend.log` and report the error.

## Troubleshooting

- **"Address already in use"**: Kill existing processes first (step 1).
- **"ECONNREFUSED" in frontend logs**: The Vite proxy target port doesn't match the backend port. Fix `frontend/vite.config.ts` (step 2).
- **Missing Python module**: Install it with `pip3 install <module>` and retry.

## Ports

- Backend: **8001**
- Frontend: **5173**
- Vite proxy in `frontend/vite.config.ts` must target **http://localhost:8001**

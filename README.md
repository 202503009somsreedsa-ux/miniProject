# Personal Finance Dashboard

A small React + Python workshop app for tracking income and expenses. Users sign in with a MiniMoth one-time code; transactions are stored in a local SQLite database.

## Requirements

- Python 3.10+
- Node.js 18+
- A MiniMoth project API key for sending real OTPs

## Run locally

1. Copy `backend/.env.example` to `backend/.env` and set `MINIMOTH_API_KEY` from your MiniMoth project. The key stays on the backend.
2. Copy `frontend/.env.example` to `frontend/.env`. The defaults work for local development.
3. In one terminal, start the API:

   ```powershell
   cd backend
   python main.py
   ```

4. In another terminal, install frontend packages and start Vite:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

5. Open the local URL printed by Vite. Enter a phone number, verify the MiniMoth code, then add income or expense transactions.

The backend creates `backend/finance.sqlite3` on first run. For local UI work without a provider key, use a MiniMoth test key; OTP requests are not simulated.

## API

- `POST /api/auth/otp/send` with `{ "phone": "+919876543210" }`
- `POST /api/auth/otp/verify` with `{ "phone": "+919876543210", "code": "123456" }`
- `GET /api/transactions` (Bearer session token)
- `POST /api/transactions` (Bearer token; description, amount, type, category)
- `DELETE /api/transactions/{id}` (Bearer token)

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. No separate CORS setup is needed.
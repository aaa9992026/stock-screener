# Stock Screener Setup

## Requirements

- Python 3
- Node.js / npm
- PostgreSQL

## Backend Setup

1. Open the backend folder:

   cd backend

2. Create a virtual environment:

   python -m venv venv

3. Activate it:

   venv\Scripts\Activate.ps1

4. Install dependencies:

   pip install -r requirements.txt

5. Create a PostgreSQL database named:

   stock_screener

6. Create a `.env` file inside the backend folder:

   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/stock_screener

7. Start the backend:

   uvicorn app.main:app --reload

Backend:

http://127.0.0.1:8000

API docs:

http://127.0.0.1:8000/docs

## Frontend Setup

1. Open the frontend folder:

   cd frontend

2. Install dependencies:

   npm install

3. Start the frontend:

   npm run dev

Frontend:

http://localhost:5173

## Initial Company Sync

After starting the backend, open the API docs and run:

POST /companies/sync/all

This imports/updates the available NSE and US company lists.

## Notes

- Historical OHLCV data is stored in PostgreSQL.
- Refreshing data updates existing dates and adds new dates without deleting normal historical records.
- API credentials should be stored in `.env`, not hard-coded in source files.
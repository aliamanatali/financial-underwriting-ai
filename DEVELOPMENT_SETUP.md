# Development Setup Guide

This guide explains how to run the OCR Document Processing application locally.

## Prerequisites

- **Python 3.8+** with `venv` support
- **Node.js 18+** and npm
- **Redis** server running locally or accessible remotely
- **Google Gemini API Key** for OCR processing

## Project Structure

```
COX/
├── ocr-backend/          # FastAPI backend server
│   ├── app/              # Application code
│   ├── venv/             # Python virtual environment
│   ├── requirements.txt  # Python dependencies
│   └── start_worker.sh   # Celery worker startup script
└── ocr-frontend/         # Next.js frontend
    ├── app/              # Next.js pages
    ├── components/       # React components
    └── package.json      # Node dependencies
```

## Setup Instructions

### 1. Backend Setup

#### Install Dependencies

```bash
cd ocr-backend

# Create virtual environment (if not exists)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows

# Install Python packages
pip install -r requirements.txt
```

#### Configure Environment Variables

Create a `.env` file in the `ocr-backend` directory:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Storage
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 2. Frontend Setup

#### Install Dependencies

```bash
cd ocr-frontend

# Install Node packages
npm install
```

#### Configure Environment Variables

Create a `.env.local` file in the `ocr-frontend` directory:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Running the Application

You need to run **three separate services** in different terminal windows:

### Terminal 1: Backend API Server

```bash
cd ocr-backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**What it does:**

- Runs the FastAPI backend server
- Handles file uploads and API requests
- Serves at `http://localhost:8000`
- Auto-reloads on code changes (`--reload` flag)

**API Documentation:**

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Terminal 2: Celery Worker

```bash
cd ocr-backend
./start_worker.sh
```

Or manually:

```bash
cd ocr-backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

**What it does:**

- Processes background tasks (PDF OCR processing)
- Handles long-running document processing jobs
- Communicates via Redis message broker

### Terminal 3: Frontend Development Server

```bash
cd ocr-frontend
npm run dev
```

**What it does:**

- Runs the Next.js development server
- Serves the web interface at `http://localhost:3000`
- Auto-reloads on code changes
- Provides hot module replacement (HMR)

## Verification

Once all three services are running:

1. **Backend API**: Visit http://localhost:8000/docs to see the API documentation
2. **Frontend**: Visit http://localhost:3000 to access the web interface
3. **Health Check**: Visit http://localhost:8000/api/health to verify backend is running

## Common Issues

### Redis Connection Error

**Error:** `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solution:**

- Ensure Redis is installed and running:

  ```bash
  # macOS (using Homebrew)
  brew services start redis

  # Linux
  sudo systemctl start redis

  # Or run Redis manually
  redis-server
  ```

### Port Already in Use

**Error:** `Address already in use`

**Solution:**

- Backend (port 8000):
  ```bash
  lsof -ti:8000 | xargs kill -9
  ```
- Frontend (port 3000):
  ```bash
  lsof -ti:3000 | xargs kill -9
  ```

### Virtual Environment Not Found

**Error:** `venv/bin/activate: No such file or directory`

**Solution:**

```bash
cd ocr-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Missing Gemini API Key

**Error:** `GEMINI_API_KEY not found`

**Solution:**

- Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
- Add it to `ocr-backend/.env`:
  ```
  GEMINI_API_KEY=your_actual_api_key_here
  ```

## Development Workflow

1. **Start all services** in separate terminals (Backend API, Celery Worker, Frontend)
2. **Make code changes** in your editor
3. **Test changes** - servers auto-reload on file changes
4. **Upload a PDF** through the frontend at http://localhost:3000
5. **Monitor processing** in the Celery worker terminal
6. **View results** in the frontend interface

## Production Deployment

For production deployment, consider:

- Use **Gunicorn** or **uWSGI** instead of Uvicorn's `--reload` mode
- Run Celery with **supervisor** or **systemd** for process management
- Use **Nginx** as a reverse proxy
- Build the Next.js app: `npm run build && npm start`
- Set appropriate environment variables for production
- Use a production-grade Redis instance
- Enable HTTPS/SSL certificates

## Stopping the Services

To stop all services:

1. Press `Ctrl+C` in each terminal window
2. Deactivate the Python virtual environment:
   ```bash
   deactivate
   ```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Redis Documentation](https://redis.io/documentation)

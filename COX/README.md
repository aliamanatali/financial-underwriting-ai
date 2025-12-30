# COX OCR Monorepo

This is a monorepo containing both the backend and frontend for the COX OCR application.

## Project Structure

```
COX/
├── ocr-backend/          # FastAPI backend with Celery for document processing
│   ├── app/              # Application code
│   ├── uploads/          # Uploaded documents (gitignored)
│   └── requirements.txt  # Python dependencies
│
├── ocr-frontend/         # Next.js frontend application
│   ├── app/              # Next.js app directory
│   ├── components/       # React components
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utility libraries
│   └── package.json      # Node.js dependencies
│
└── README.md             # This file
```

## Getting Started

### Backend Setup

```bash
cd ocr-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Configure your .env file
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd ocr-frontend
npm install
cp .env.local.example .env.local
# Configure your .env.local file
npm run dev
```

## Documentation

- Backend documentation: See [ocr-backend/README.md](ocr-backend/README.md)
- Frontend documentation: See [ocr-frontend/README.md](ocr-frontend/README.md)

## Technologies

- **Backend**: Python, FastAPI, Celery, Redis, Google Gemini API
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS

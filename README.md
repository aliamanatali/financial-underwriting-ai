# Financial Underwriting AI - Complete Platform

A comprehensive financial underwriting platform combining OCR document extraction, financial data processing, and analysis capabilities.

## 🎯 Project Overview

This platform provides end-to-end financial document processing and underwriting analysis:

1. **OCR Backend** - High-fidelity PDF text extraction using Google Gemini API
2. **OCR Frontend** - Next.js web interface for document management and viewing
3. **Financial Engine** - Data normalization, ingestion, and financial analysis

## 📁 Project Structure

```
financial_underwriting-ai/
├── ocr-backend/              # FastAPI backend for document OCR
│   ├── app/
│   │   ├── api/             # API routes
│   │   ├── services/        # Business logic (Gemini, storage, etc.)
│   │   ├── tasks/           # Celery background tasks
│   │   ├── models/          # Data models
│   │   └── utils/           # Utilities
│   ├── requirements.txt
│   └── README.md
│
├── ocr-frontend/            # Next.js frontend application
│   ├── app/                 # Next.js app directory
│   │   ├── documents/       # Document viewing pages
│   │   ├── analysis/        # Financial analysis pages
│   │   └── upload/          # Upload interface
│   ├── components/          # React components
│   │   ├── DocumentList.tsx
│   │   ├── DocumentViewer.tsx
│   │   ├── FinancialAnalysis.tsx
│   │   ├── UnderwritingDashboard.tsx
│   │   ├── AuditTrailWidget.tsx
│   │   └── ExportButtons.tsx
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # API client and types
│   ├── package.json
│   └── README.md
│
├── financial-engine/        # Financial data processing
│   ├── app/
│   │   └── services/        # Financial services
│   │       ├── ingestion_service.py
│   │       ├── normalization_service.py
│   │       ├── financial_service.py
│   │       ├── excel_service.py
│   │       ├── gemini_client.py
│   │       ├── memo_service.py
│   │       ├── audit_log_service.py
│   │       └── ocr_backend_client.py
│   ├── requirements.txt
│   └── main.py
│
├── extraction_pipeline/     # Data extraction schemas
├── PROJECT_COMPLETION_REPORT.md
├── QUALITY_ASSURANCE_AUDIT.md
├── CONSOLIDATION_PLAN.md
└── DEVELOPMENT_SETUP.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Redis (for Celery background tasks)
- Google Gemini API key

### 1. OCR Backend Setup

```bash
cd ocr-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
uvicorn app.main:app --reload
```

The backend will be available at `http://localhost:8000`

### 2. OCR Frontend Setup

```bash
cd ocr-frontend
npm install
cp .env.local.example .env.local
# Edit .env.local and configure API endpoint
npm run dev
```

The frontend will be available at `http://localhost:3000`

### 3. Financial Engine Setup

```bash
cd financial-engine
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 🔑 Key Features

### OCR Backend

- ✅ **Gemini-Powered Extraction** - Uses Google Gemini 1.5 Pro for accurate PDF text extraction
- ✅ **Zero Hallucination** - DocuMind prompt approach ensures faithful document digitization
- ✅ **Celery Background Processing** - Async task processing with Redis
- ✅ **Real-time Progress Updates** - Server-Sent Events (SSE) for live progress tracking
- ✅ **PDF Chunking** - Handles large documents by processing in chunks
- ✅ **Flexible Storage** - Local file storage or MinIO object storage
- ✅ **Normalization Service** - Data normalization capabilities

### OCR Frontend

- ✅ **Document Management** - Upload, view, and delete documents
- ✅ **Real-time Progress** - Live updates during document processing
- ✅ **Document Viewer** - View extracted text with metadata
- ✅ **Financial Analysis** - Integrated financial analysis dashboard
- ✅ **Underwriting Dashboard** - Comprehensive underwriting metrics
- ✅ **Audit Trail** - Track document processing history
- ✅ **Export Capabilities** - Export data in multiple formats
- ✅ **Responsive Design** - Works on desktop and mobile

### Financial Engine

- ✅ **Data Ingestion** - Import from Excel, PDFs, and other sources
- ✅ **Normalization** - Standardize financial data formats
- ✅ **Financial Analysis** - Calculate key metrics and ratios
- ✅ **Memo Generation** - Automated financial memo creation
- ✅ **Audit Logging** - Track all data transformations
- ✅ **OCR Integration** - Seamless integration with OCR backend
- ✅ **Gemini AI** - AI-powered data extraction and analysis

## 📚 Documentation

- **OCR Backend**: See [ocr-backend/README.md](ocr-backend/README.md)
- **OCR Frontend**: See [ocr-frontend/README.md](ocr-frontend/README.md) and integration guides
- **Development Setup**: See [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)
- **Project Completion**: See [PROJECT_COMPLETION_REPORT.md](PROJECT_COMPLETION_REPORT.md)
- **Quality Assurance**: See [QUALITY_ASSURANCE_AUDIT.md](QUALITY_ASSURANCE_AUDIT.md)
- **Consolidation Details**: See [CONSOLIDATION_PLAN.md](CONSOLIDATION_PLAN.md)

## 🔧 Technology Stack

### Backend

- **Python** - FastAPI, Celery, Redis
- **AI/ML** - Google Gemini API
- **Storage** - Local filesystem or MinIO
- **Database** - MongoDB (optional)

### Frontend

- **Framework** - Next.js 16, React 19
- **Language** - TypeScript
- **Styling** - Tailwind CSS 4
- **State Management** - React Hooks
- **API Communication** - Fetch API with SSE

### Financial Engine

- **Python** - FastAPI, Pydantic
- **Data Processing** - openpyxl, pandas-like operations
- **AI** - Google Gemini for intelligent extraction

## 🔄 Workflow

1. **Upload Document** → OCR Frontend uploads PDF to OCR Backend
2. **Process Document** → Backend extracts text using Gemini API
3. **Real-time Updates** → Frontend receives progress via SSE
4. **View Results** → Extracted text displayed in Document Viewer
5. **Financial Analysis** → Data sent to Financial Engine for processing
6. **Generate Reports** → Financial metrics and memos generated
7. **Export Data** → Results exported in desired format

## 🧪 Testing

Each component has its own test suite:

```bash
# OCR Backend
cd ocr-backend
pytest

# OCR Frontend
cd ocr-frontend
npm test

# Financial Engine
cd financial-engine
pytest
```

## 📝 Environment Variables

### OCR Backend (.env)

```bash
GEMINI_API_KEY=your_api_key_here
REDIS_URL=redis://localhost:6379/0
UPLOAD_DIR=./uploads
```

### OCR Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🤝 Contributing

This is a consolidated project combining multiple features. When contributing:

1. Identify which component you're modifying (backend/frontend/engine)
2. Follow the existing code style and patterns
3. Update relevant documentation
4. Test your changes thoroughly

## 📄 License

This project is provided as-is for financial underwriting purposes.

## 🙏 Acknowledgments

- Based on the MTD (Motion to Dismiss) project's document extraction implementation
- Consolidated from multiple project instances into a unified platform
- Powered by Google Gemini AI for intelligent document processing

## 📞 Support

For issues or questions:

1. Check the component-specific README files
2. Review the API documentation at `/docs` (backend)
3. Check the consolidation plan for architecture details
4. Review logs for error details

---

**Note**: This project was consolidated from three separate instances. See [CONSOLIDATION_PLAN.md](CONSOLIDATION_PLAN.md) for details on the consolidation process and feature preservation.

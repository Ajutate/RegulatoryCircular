# Regulatory Circular Analyzer — GenAI Application

A Python application that uses **LangChain + LiteLLM** to analyze regulatory 
circulars (PDF/DOCX) and export paragraph-level classifications to Excel. It now features a complete **Maker-Checker workflow** backed by SQLite.

## Features

- 📤 Upload PDF or DOCX regulatory documents
- 🤖 AI-powered classification of each paragraph across 10 dimensions
- 👥 **Maker-Checker Workflow**: Makers upload/review AI drafts, Checkers approve/reject.
- 🔐 **Role-based Auth**: Segregated views and queues for Makers, Checkers, and Admins.
- ⚙️ **Admin Dashboard**: Live prompt management and overrides.
- 📊 Interactive results table with filters, row-level regeneration, and edits.
- 📥 Styled Excel export with conditional formatting

## Columns Generated

| # | Column | Example Values |
|---|--------|---------------|
| 1 | Regulator Para Type | Action Para, Information Para |
| 2 | Is Effective Date Provided | Yes / No |
| 3 | Regulatory Para Effective Date | DD/MM/YYYY |
| 4 | Business Unit | Administration, Audit, Compliance - RRD |
| 5 | Theme | Monitoring, Process, Reporting |
| 6 | Control Object Name | Risk, Communication, Process and Policy |
| 7 | Actionable | Description of action required |
| 8 | Level 1 | Governance, Due Diligence |
| 9 | Level 2 | Corporate Governance, Access Control |
| 10 | Level 3 | Fit and Proper Criteria, Customer Communication |

## Technology Stack

- **LangChain** (🦜): Orchestration of the LLM analysis chain.
- **FastAPI** (⚡): High-performance async web backend.
- **LiteLLM Proxy** (🔗): Unified API interface for local (Ollama) and cloud models.
- **PyMuPDF** (📄): Robust PDF parsing, OCR, and geometric Block extraction.
- **SQLAlchemy/SQLite** (🗄️): Persistent state, user auth, and Maker/Checker queues.
- **OpenPyXL** (📊): Excel file generation with conditional formatting.
- **Pydantic** (🐍): Data validation and structured output parsing.
- **Bootstrap 5** (🥾): Responsive UI framework.

## Project Structure

```text
RegulatoryCircular/
├── .env                          # LiteLLM config (update with your values)
├── requirements.txt
├── server.py                     # FastAPI app (REST API + static file server)
│
├── static/
│   ├── index.html                # Landing page
│   ├── login.html                # Auth page
│   ├── upload.html               # Document Upload (Maker)
│   ├── maker.html                # Maker dashboard and queue
│   ├── maker_review.html         # Maker AI review screen
│   ├── checker.html              # Checker queue and approval screen
│   ├── admin.html                # Admin dashboard (Prompt Management)
│   ├── css/style.css             # Shared mobile-first design system
│   └── js/                       # Frontend JS for all views (app.js, maker.js, checker.js, etc.)
│
├── config/
│   └── settings.py               # Pydantic BaseSettings (auto-loads .env)
│
├── core/
│   ├── llm.py                    # LLM client factory (LiteLLM proxy)
│   ├── schemas.py                # Pydantic models for structured output
│   ├── prompts.py                # System & user prompt templates
│   └── logger.py                 # Custom UTF-8 logger configuration
│
└── services/
    ├── document_extractor.py     # PDF/DOCX geometric Block extraction
    ├── paragraph_splitter.py     # Structural paragraph segregation
    ├── regulatory_analyzer.py    # LangChain analysis chain
    ├── excel_exporter.py         # Excel generation
    └── database.py               # SQLAlchemy models (Users, Documents, Prompts)
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the LiteLLM Proxy

This application uses [LiteLLM](https://docs.litellm.ai/) as a unified gateway to translate standard OpenAI-formatted API requests into local Ollama commands (or route them to cloud providers like Gemini/OpenAI).

A pre-configured `litellm_config.yaml` is included. It defines several local models (e.g. `ollama/llama3.1`, `ollama/qwen2.5:7b`) and sets up a proxy server on port `4000` with a dummy master key.

To start the proxy, ensure you have [Ollama](https://ollama.com/) running (`ollama serve`), then run:
```bash
litellm --config litellm_config.yaml
```

*(Note: The config file also contains instructions at the bottom for migrating from local Ollama to cloud-based Gemini 2.5 Flash with zero code changes!)*

### 3. Configure the Application Environment

Edit the `.env` file to point to your running LiteLLM proxy:

```env
LITELLM_BASE_URL=http://localhost:4000
LITELLM_API_KEY=sk-dummy-key
LLM_MODEL=ollama/llama3.1
LLM_TEMPERATURE=0.1
```

### 4. Run the Server

```bash
python -m uvicorn server:app --port 8000 --reload
```

The app opens at `http://localhost:8000`. Default users created on startup:
- `admin` / `admin`
- `maker` / `maker` (plus maker2, maker3)
- `checker` / `checker` (plus checker2, checker3)

## Replacing the Document Extractor

The `services/document_extractor.py` module is designed to be replaceable.
To swap in an API-backed extractor:

```python
class APIDocumentExtractor(DocumentExtractor):
    def extract(self, file_bytes: bytes, file_name: str) -> str:
        import requests
        resp = requests.post(
            "https://your-api/extract",
            files={"file": (file_name, file_bytes)},
        )
        return resp.json()["text"]
```

No other files need to change — just update `server.py` (in the `/api/upload` endpoint) to 
use `APIDocumentExtractor` instead of `DocumentExtractor`.

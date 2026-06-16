# 📄 ResumeAI — Resume Analyzer

A full-stack resume analysis tool.
Upload a PDF, get ATS score, match against job descriptions, see improvement tips.

**Stack:** FastAPI · React · Vite · Tailwind CSS · spaCy · pdfplumber · SQLite

---

## ⚡ Quick Start

### 1. Clone / Extract the project

```bash
cd resume-analyzer
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Download the spaCy English NLP model (required!)
python -m spacy download en_core_web_sm

# Start the API server
uvicorn main:app --reload --port 8000
```

✅ Backend running at: http://localhost:8000  
📖 Auto API docs at: http://localhost:8000/docs

### 3. Frontend Setup (new terminal)

```bash
cd frontend

npm install
npm run dev
```

✅ Frontend running at: http://localhost:5173

---

## 🔌 API Endpoints

| Method | URL                       | What it does                        |
|--------|---------------------------|-------------------------------------|
| GET    | `/`                       | Health check                        |
| POST   | `/upload-resume`          | Upload PDF, extract + parse         |
| POST   | `/analyze-resume`         | Calculate ATS score                 |
| POST   | `/match-job-description`  | Compare resume vs job description   |
| GET    | `/history`                | Get past analyses from SQLite       |

---

## 🧠 ATS Score Formula
# Tender Desk — AI-Powered Tender Intelligence and Decision Support

An AI-powered tender analysis platform that helps users understand construction tender documents, retrieve relevant clauses, verify eligibility requirements, compare tenders, and make informed bidding decisions.

Upload tender PDFs, ask questions in natural language, receive answers with page-level citations, extract important tender information, and evaluate contractor eligibility through an interactive interface.

## Overview

Tender Desk combines **Retrieval-Augmented Generation (RAG), hybrid information retrieval, document processing, and structured LLM-based analysis** to simplify tender document review.

### Technology Stack

**Backend**
- Python
- Flask and Flask-CORS
- PyMuPDF and pdfplumber
- Tesseract OCR
- LangChain
- Sentence Transformers — BAAI/bge-base-en-v1.5
- FAISS
- BM25
- Groq API

**Frontend**
- React 18
- Vite
- JavaScript
- CSS

**Retrieval architecture**
- Dense vector retrieval using BGE embeddings
- Lexical retrieval using BM25
- Reciprocal Rank Fusion (RRF)
- Page-aware document chunking
- Citation validation and evidence verification

**LLM configuration**

The LLM provider and model are configurable through environment variables. The example configuration uses `openai/gpt-oss-20b` through Groq.

## Features

| Feature | Description |
|---|---|
| Multi-tender management | Upload and manage multiple tender documents, each with its own index |
| RAG-based Q&A | Ask natural-language questions and receive answers grounded in tender content |
| Page-level citations | Trace generated answers back to supporting PDF pages |
| Hybrid retrieval | Combine dense semantic search and BM25 keyword search using RRF |
| Exact clause search | Find specific words, phrases, and clauses using lexical retrieval |
| Key information extraction | Extract EMD, tender fee, security deposit, completion period, deadlines, and bid validity |
| Eligibility analysis | Identify eligibility requirements and evaluate contractor information |
| Risk analysis | Examine liquidated damages, termination, payment, escalation, and retention clauses |
| BOQ analysis | Analyze available BOQ and pricing information |
| Tender comparison | Compare two tender documents or revisions |
| PDF export | Export analysis and summary information into PDF reports |

## System Architecture

The application follows a modular document-processing and RAG pipeline.

1. **Document ingestion:** Extract text using PyMuPDF. Use OCR for scanned pages without a usable text layer and pdfplumber for table extraction.
2. **Preprocessing:** Clean extracted text, remove recurring headers and footers, and identify document sections.
3. **Chunking:** Split prose into overlapping chunks while preserving table structure and repeating headers where required.
4. **Embedding and indexing:** Generate BGE embeddings and store them in a separate FAISS index for each tender.
5. **Hybrid retrieval:** Retrieve relevant passages through dense semantic search and BM25 lexical search, then combine rankings using Reciprocal Rank Fusion.
6. **Answer generation:** Provide retrieved evidence to the LLM and generate grounded answers with source references.
7. **Citation validation:** Validate generated source references and map them back to the original PDF page numbers.
8. **Structured analysis:** Extract tender information using predefined schemas and cache results to reduce repeated LLM calls.

## Retrieval and Evaluation

The system was evaluated using a manually prepared benchmark containing **30 questions across two tender documents**.

The evaluation covers:
- Answer correctness
- Citation hit rate
- Citation precision
- Strict citation correctness
- Evidence coverage
- Page-level retrieval performance
- Text-level retrieval performance
- Mean Reciprocal Rank (MRR)

### v3 vs. v4 comparison

The following results represent the reported 30-question comparison between the v3 and v4 evaluation runs.

| Metric | v3 | v4 |
|---|---:|---:|
| Answer accuracy | 28/30 (93%) | **30/30 (100%)** |
| Citation hit | 29/30 (97%) | **30/30 (100%)** |
| Citation precision | 0.88 | **0.92** |
| Strict citation correctness | 80% | **83%** |
| Evidence coverage | 0.78 | **0.81** |
| Page Hit@1 | 0.80 | 0.80 |
| Page Hit@3 | 1.00 | 1.00 |
| Page Hit@6 | 1.00 | 1.00 |
| Page MRR@6 | 0.89 | 0.89 |
| Text Hit@1 | 0.62 | 0.62 |
| Text Hit@3 | 0.86 | 0.86 |
| Text Hit@6 | 0.93 | 0.93 |
| Text MRR@6 | 0.74 | 0.74 |
| Mean confidence | 0.79 | 0.80 |

### Evaluation observations

- The v4 run achieved 30/30 answer checks, compared with 28/30 in v3.
- Citation hit rate increased from 29/30 to 30/30.
- Citation precision improved from 0.88 to 0.92.
- Evidence coverage improved from 0.78 to 0.81.
- All eight reported retrieval-ranking measurements remained identical.

**Important interpretation:** The results indicate improvements in answer generation and citation handling. They do not demonstrate an improvement in retrieval ranking, since the measured retrieval metrics were unchanged.

The benchmark is limited to the evaluated questions and documents. These results should not be interpreted as a guarantee of correctness on arbitrary tenders.

## Confidence Scoring

Tender Desk uses a transparent heuristic confidence score:

`Confidence = 0.6 × mean similarity of cited passages + 0.4 × share of valid citations`

The application categorizes scores as:

- **High:** 0.70 or above
- **Medium:** 0.50 to below 0.70
- **Low:** Below 0.50

This is a heuristic indicator, not a statistically calibrated probability that an answer is correct.

## Project Structure

```text
tender-intelligence-v2/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
│
├── chunking/
│   └── chunker.py
│
├── config/
│   └── settings.py
│
├── embeddings/
│   └── embedder.py
│
├── ingestion/
│   ├── document_processor.py
│   ├── ingest.py
│   ├── ocr.py
│   ├── pdf_loader.py
│   └── table_extractor.py
│
├── preprocessing/
│   ├── section_detector.py
│   └── text_cleaner.py
│
├── vectorstore/
│   ├── faiss_store.py
│   └── retriever.py
│
├── rag/
│   ├── answer_generator.py
│   ├── citation_validator.py
│   ├── pipeline.py
│   └── query_expansion.py
│
├── llm/
│   ├── groq_client.py
│   └── prompts.py
│
├── intelligence/
│   ├── bid_checker.py
│   ├── cache.py
│   ├── catalog.py
│   ├── compare.py
│   ├── export_pdf.py
│   └── extractor.py
│
├── evaluation/
│   ├── eval_qa.py
│   ├── eval_qa_v2.py
│   ├── eval_qa_v3.py
│   ├── eval_qa_v4.py
│   └── eval_retrieval.py
│
├── tests/
│
├── data/
│   ├── uploads/
│   ├── processed/
│   ├── vectorstore/
│   └── cache/
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── api.js
        ├── main.jsx
        ├── styles.css
        └── components/
```

## Installation and Setup

### Prerequisites

- Python 3.10 or later
- Node.js 18 or later
- npm
- Groq API key
- Tesseract OCR (required for scanned-document OCR)

### 1. Clone the repository

```bash
git clone https://github.com/Arin-12/tender-desk.git
cd tender-desk
```

### 2. Set up the backend

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```powershell
copy .env.example .env
```

Open `.env` and configure your Groq API key:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

The LLM model, embedding model, OCR settings, chunking configuration, and server settings can also be configured in this file.

### 3. Configure Tesseract OCR

Install Tesseract OCR and set its executable path in `.env` if it is not automatically available:

```dotenv
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_ENABLED=true
```

### 4. Start the backend

```bash
python app.py
```

The backend runs at:

```text
http://127.0.0.1:5000
```

### 5. Set up the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at:

```text
http://localhost:5173
```

Vite proxies API requests to the Flask backend.

## Running Tests

Run the test suite from the project root:

```bash
python -m pytest tests
```

## API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/documents` | List uploaded tenders |
| POST | `/api/upload` | Upload a tender PDF |
| DELETE | `/api/documents/<id>` | Delete a tender |
| POST | `/api/chat` | Ask questions using RAG |
| POST | `/api/search` | Search tender content |
| POST | `/api/analyze` | Perform structured tender analysis |
| POST | `/api/eligibility/check` | Check contractor eligibility |
| POST | `/api/compare` | Compare two tenders |
| GET | `/api/export/<id>` | Export a PDF report |

The analysis endpoint supports the configured analysis types, including key information, summary, eligibility, risks, and BOQ.

## Limitations

- OCR on large scanned PDFs can be time-consuming.
- Tables without detectable ruling lines or clear structure may not be extracted correctly.
- LLM outputs can contain errors or omit relevant clauses.
- Groq API rate limits may affect larger analysis and comparison operations.
- Retrieval and answer quality depend on document quality, chunking, retrieval settings, and the question asked.
- Eligibility and financial interpretations require human verification.

Tender Desk is intended as a decision-support tool. It does not replace professional tender review or verification of original tender documents.

## Security

- API credentials are stored in `.env` and should never be committed to Git.
- `.env.example` contains configuration placeholders only.
- Uploaded PDFs, processed documents, vector indexes, and caches are kept out of the public repository by `.gitignore`.
- Answers and extracted tender details should always be verified against the original documents.

## Future Scope

- Improved table and scanned-document understanding
- More robust retrieval and reranking
- Advanced multimodal tender analysis
- Tender deadline tracking and notifications
- Multilingual support
- E-tender portal integration
- More comprehensive evaluation across diverse tender types


---

**Developed as an AI-powered tender intelligence and decision-support project.**

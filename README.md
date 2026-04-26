# Wiki LLM Document Assistant

Wiki LLM Document Assistant is a full-stack AI-powered application designed to ingest, index, search, and generate or edit DOCX documents using Google's Gemini LLMs. It acts as an intelligent document management and drafting system, ideal for contracts, proposals, and other structured documents.

## 🚀 Key Features

*   **Intelligent Ingestion:** Parses raw PDF and DOCX files, extracting complete text and structure into Markdown, semantic chunks, and generating metadata-rich JSON summaries.
*   **Semantic Retrieval:** Employs Gemini 2.0 Flash Lite to perform "whole-index" smart routing and retrieval, finding the most relevant templates or reference documents based on user queries and category filters.
*   **Automated Drafting & Editing:** Uses Gemini 1.5 Pro to plan changes and Gemini 1.5 Flash to write structured DOCX files. It can create new documents from scratch or apply targeted edits to existing templates while preserving run-level formatting.
*   **Modern Web Dashboard:** A sleek, responsive Next.js (React 19) frontend built with TailwindCSS for managing the document library, triggering tasks, and reviewing task history.
*   **Unified CLI & REST API:** Core operations can be executed via a command-line interface or through the FastAPI REST endpoints.

## 🛠️ Tech Stack

*   **Backend:** Python 3.12+, FastAPI, Uvicorn, google-genai, python-docx
*   **Frontend:** Next.js (React 19), Tailwind CSS v4, Lucide React, Axios
*   **AI Models:**
    *   *Gemini 2.0 Flash Lite* (Document parsing, summarization, routing/retrieval)
    *   *Gemini 1.5 Pro* (Task planning)
    *   *Gemini 1.5 Flash* (Document generation/writing)
*   **Package Management:** `uv` (Python), `npm` (Node.js)

## 📂 Project Structure

```text
wiki-llm-document-assistance/
├── main.py              # CLI entrypoint for all tools
├── pyproject.toml       # Python dependencies and metadata
├── server/              # FastAPI application
│   └── app.py           # REST API endpoints
├── tools/               # Core business logic and LLM interactions
│   ├── ingest.py        # File processing and summarization
│   ├── query.py         # Smart retrieval routing
│   ├── task.py          # Document generation orchestration
│   ├── docx_writer.py   # DOCX creation and editing logic
│   └── utils.py         # Helpers, Gemini API wrapper, hashing
├── web/                 # Next.js frontend application
│   ├── package.json
│   └── src/app/         # React components and pages
├── raw/                 # (Created dynamically) Uploaded/raw documents
├── processed/           # (Created dynamically) Ingested markdown, chunks, summaries, and index
└── output/              # (Created dynamically) Generated DOCX files
```

## ⚙️ Core Processes

### 1. Document Ingestion (`tools/ingest.py`)
1.  **Scanning:** Reads PDF/DOCX files from the `raw/` directory.
2.  **Extraction:** Sends files to Gemini Vision to extract pristine Markdown, preserving headings and tables.
3.  **Chunking:** Splits the Markdown into semantic chunks for localized context.
4.  **Summarization:** Analyzes the full document text (up to 200k characters) to generate a structured JSON summary (metadata, hash, keywords, etc.).
5.  **Indexing:** Compiles all summaries into a central `index.json` for fast retrieval.

### 2. Smart Querying (`tools/query.py`)
1.  **Routing:** Sends the user's prompt and a minimized catalog of available documents to Gemini.
2.  **Scoring:** The LLM returns the top-K relevant documents with a match score and reasoning.
3.  **Fallback:** If the LLM fails, falls back to a weighted keyword matching algorithm.

### 3. Task Execution (`tools/task.py` & `tools/docx_writer.py`)
1.  **Context Gathering:** Retrieves relevant documents using the query module.
2.  **Planning:** Uses Gemini 1.5 Pro to formulate an execution plan based on the user prompt, retrieved context, and any specified style templates.
3.  **Writing:** Uses Gemini 1.5 Flash to execute the plan, outputting structured JSON with text replacements or raw content.
4.  **Document Assembly:** `docx_writer.py` either creates a new document or surgically replaces text in an existing template, preserving run-level formatting where possible.

## 💻 Setup & Installation

### Prerequisites
*   Python 3.12 or higher
*   Node.js 20 or higher
*   [uv](https://docs.astral.sh/uv/) (Python package installer)
*   A valid [Google Gemini API Key](https://aistudio.google.com/app/apikey)

### 1. Backend Setup

```bash
# Clone the repository
git clone <repository-url>
cd wiki-llm-document-assistance

# Set up environment variables
cp .env.example .env
# Open .env and insert your actual API key:
# GEMINI_API_KEY="your_api_key_here"

# Install Python dependencies using uv
uv sync
```

### 2. Frontend Setup

```bash
cd web
npm install
```

## 🚀 Running the Application

To use the web dashboard, you need to run both the FastAPI backend and the Next.js frontend concurrently.

### 1. Start the Backend Server

Open a terminal in the root directory and run:
```bash
python main.py serve
```
*The API will be available at `http://localhost:8000`*

### 2. Start the Frontend Server

Open a new terminal in the `web/` directory and run:
```bash
npm run dev
```
*The Dashboard will be available at `http://localhost:3000`*

## ⌨️ CLI Usage

You can bypass the web UI and use the unified CLI script `main.py` to trigger operations directly.

```bash
# Ingest all files from the raw directory
python main.py ingest ./raw

# Query the index for a specific topic
python main.py query "confidentiality agreement"

# Start a document generation task
python main.py start "Write a new employment contract for John Doe"
```

## 🔮 Future Improvements

*   **Vector Database Integration:** Migrate from in-memory JSON matching to a scalable Vector DB (e.g., ChromaDB, Qdrant) for improved semantic search over thousands of documents.
*   **Streaming Responses:** Implement WebSockets or Server-Sent Events (SSE) to stream LLM generation progress to the frontend UI.
*   **Advanced Formatting Preservation:** Improve the `docx_writer` to handle complex multi-run formatting bridging, tables, and nested lists more elegantly during text replacement.

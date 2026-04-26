import os

# Default Model Names
DEFAULT_INGEST_MODEL = os.getenv("INGEST_MODEL", "gemini-2.0-flash")
DEFAULT_READING_MODEL = os.getenv("READING_MODEL", "gemini-2.0-flash")
DEFAULT_WRITING_MODEL = os.getenv("WRITING_MODEL", "gemini-2.0-flash")

# Legacy fallback
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_INGEST_MODEL)

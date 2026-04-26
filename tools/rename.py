import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from tools.config import DEFAULT_INGEST_MODEL
from tools.utils import call_gemini, parse_json_from_response, REPO_ROOT

def auto_rename(file_path_str: str):
    file_path = Path(file_path_str)
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
        
    print(f"Analyzing {file_path.name}...")
    
    today = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y%m%d")
    
    prompt = f"""You are an expert document classifier.
Analyze the attached document and classify it based on the following strict rules:

1. Directory Structure:
- 01_Templates: Blank forms or templates.
- 02_Library_Assets: Reusable assets (CVs, partner profiles, general Letters of Support).
- 03_Projects_Archive: Specific project files (e.g., 2024_VoiceAI_BV175, 2024_VinIF_DLD_SSD, 2025_Terumo_BrainTrain, 2026_SVI_Grant).
- 04_References: Reference materials, examples from other projects, guidelines.

2. Naming Convention: YYYYMMDD_[Scope]_[Type]_[Subject]_[Status]_[vX].[ext]
The YYYYMMDD is already provided: {today}
The [ext] is already provided: {file_path.suffix}

3. Valid [Scope] values:
BK, IU, ND2, BV175, VinIF, Terumo, SVI, Common

4. Valid [Type] values:
CV (Curriculum Vitae), PRO (Proposal), CON (Contract/Agreement), ETH (Ethics/IRB), BUD (Budget/Finance), REQ (Request Letter), ADM (Admin/Support/LoS), REP (Report), SCH (Schedule), PRE (Presentation), CRF (Case Report Form), FIG (Figure), GDL (Guideline), COR (Correspondence).

Analyze the document, determine its purpose, and propose a new filename and the exact destination directory path (e.g., '02_Library_Assets/Team_CVs' or '03_Projects_Archive/2026_SVI_Grant').

Return ONLY a JSON object with these exact keys:
{{
  "proposed_name": "...",
  "destination_folder": "...",
  "reasoning": "A brief explanation of why you chose this name and folder."
}}
"""

    model_name = DEFAULT_INGEST_MODEL
    
    try:
        response_text = call_gemini(prompt, max_tokens=1024, model_override=model_name, file_path=file_path)
        result = parse_json_from_response(response_text)
    except Exception as e:
        print(f"Error classifying document: {e}")
        sys.exit(1)
        
    proposed_name = result.get("proposed_name")
    destination_folder = result.get("destination_folder")
    reasoning = result.get("reasoning")
    
    if not proposed_name or not destination_folder:
        print("Error: LLM returned incomplete data.")
        print(result)
        sys.exit(1)
        
    print("\n--- Classification Result ---")
    print(f"Proposed Name: {proposed_name}")
    print(f"Destination:   {destination_folder}/")
    print(f"Reasoning:     {reasoning}")
    print("-----------------------------\n")
    
    confirm = input("Do you want to apply this rename and move? (y/n): ").strip().lower()
    
    if confirm == 'y':
        dest_dir = REPO_ROOT / destination_folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        new_file_path = dest_dir / proposed_name
        if new_file_path.exists():
            print(f"Error: Target file already exists: {new_file_path}")
            sys.exit(1)
            
        shutil.move(str(file_path), str(new_file_path))
        print(f"Success! Moved to {new_file_path}")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/rename.py <path_to_file>")
        sys.exit(1)
    auto_rename(sys.argv[1])

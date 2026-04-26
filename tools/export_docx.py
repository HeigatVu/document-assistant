import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from tools.docx_writer import create_docx, clone_and_fill

def main():
    parser = argparse.ArgumentParser(description="Export JSON content to DOCX.")
    parser.add_argument("input_json", help="Path to input JSON file")
    parser.add_argument("output_docx", help="Path to output DOCX file")
    parser.add_argument("--template", help="Path to template DOCX file for cloning/replacement")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_json)
    output_path = Path(args.output_docx)
    
    if not input_path.exists():
        print(f"Error: Input JSON not found: {input_path}")
        sys.exit(1)
        
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)
        
    try:
        if args.template:
            template_path = Path(args.template)
            if not template_path.exists():
                print(f"Error: Template not found: {template_path}")
                sys.exit(1)
            clone_and_fill(template_path, data, output_path)
        else:
            create_docx(data, output_path)
            
        print(f"Successfully exported to {output_path}")
    except Exception as e:
        print(f"Error during export: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

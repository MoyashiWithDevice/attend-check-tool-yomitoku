import sys
import os
import argparse
import json
import glob
from pathlib import Path
from tqdm import tqdm
from .config_schema import AttendCheckConfig
from .extractor import Extractor
from .writer import CSVWriter
from yomitoku.document_analyzer import DocumentAnalyzer
from typing import List

# Default Config Path
CONFIG_FILE = "backend/config/config.json"

def load_config() -> AttendCheckConfig:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            return AttendCheckConfig(**data)
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}. Using defaults.")
            return AttendCheckConfig()
    else:
        # Create default if not exists
        return AttendCheckConfig()

def get_input_files(input_path: str) -> List[str]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {input_path}")
    
    if path.is_file():
        return [str(path)]
    
    # If dir, scan for images
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".pdf"}
    files = []
    for f in path.rglob("*"):
        if f.suffix.lower() in extensions:
            files.append(str(f))
    return files

def main():
    parser = argparse.ArgumentParser(description="AttendCheck - Attendance List Generator")
    parser.add_argument("input_path", nargs="?", help="Input image file or directory")
    parser.add_argument("-o", "--output", default="results", help="Output directory")
    parser.add_argument("--merge", action="store_true", help="Merge all results into one CSV")
    parser.add_argument("--split", action="store_true", help="Save separate CSV for each image")
    parser.add_argument("--device", default="cpu", help="Device (cpu/cuda)")
    
    args = parser.parse_args()

    # 1. Interactive Input (if needed)
    input_path = args.input_path
    if not input_path:
        print(">>> Please enter the path to the image(s) or folder:")
        input_path = input("Path: ").strip().strip('"') # Remove quotes if user added them
    
    try:
        files = get_input_files(input_path)
    except FileNotFoundError:
        print("Error: File or directory not found.")
        return
    except Exception as e:
        print(f"Error: {e}")
        return

    if not files:
        print("No valid image files found.")
        return

    print(f"Found {len(files)} files to process.")

    # 2. Config & Initialization
    config = load_config()
    extractor = Extractor(config)
    
    # Initialize Yomitoku Analyzer
    # Using defaults for configs as they should handle model downloading
    print("Initializing OCR Engine (this may take a while)...")
    try:
        analyzer = DocumentAnalyzer(
            device=args.device,
            visualize=False # We don't need vis for this tool
        )
    except Exception as e:
        print(f"Failed to initialize OCR Engine: {e}")
        return

    # 3. Processing
    all_results = []
    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    mode = "ask"
    if args.merge: mode = "merge"
    elif args.split: mode = "split"

    for fpath in tqdm(files, desc="Processing"):
        try:
            # Load Image using yomitoku functions
            from yomitoku.data.functions import load_image, load_pdf
            
            p = Path(fpath)
            if p.suffix.lower() == ".pdf":
                 # PDF loading returns list of images
                imgs = load_pdf(p)
            else:
                imgs = load_image(p) # Returns list of images (usually 1 for single image)

            file_students = []
            for i, img in enumerate(imgs):
                # Analyze image
                result, _, _ = analyzer(img)
                
                # Extract student info
                students = extractor.extract(result, file_name=os.path.basename(fpath))
                file_students.extend(students)
            
            all_results.extend(file_students)
            
        except Exception as e:
            print(f"\nError processing {fpath}: {e}")
            continue

    # 4. Output Selection
    if mode == "ask":
        print("\nProcessing complete.")
        print("How would you like to save the results?")
        print("1. Merge all into one CSV (results.csv)")
        print("2. Split into separate CSVs per image")
        choice = input("Select [1/2]: ").strip()
        if choice == "1":
            mode = "merge"
        else:
            mode = "split"

    if mode == "merge":
         out_path = os.path.join(out_dir, "attendance_list.csv")
         CSVWriter.write_merged(all_results, out_path)
         print(f"saved to {out_path}")
    else:
        # For split, we need to regroup by file...
        # Or we could have saved them during the loop.
        # Since we collected them flat, let's group them back.
        grouped = {}
        for s in all_results:
            if s.file_name not in grouped:
                grouped[s.file_name] = []
            grouped[s.file_name].append(s)
        
        for fname, students in grouped.items():
            CSVWriter.write_split(students, fname, out_dir)
        print(f"Saved {len(grouped)} CSV files to {out_dir}")

if __name__ == "__main__":
    main()

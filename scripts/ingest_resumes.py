"""
Ingest resumes from a folder into data/resumes.csv.
Supports: .pdf, .docx, .txt, and .csv files.

Usage (PowerShell):
  Set-Location 'D:\Resume Analysis\ResumeAnalysis'
  .\.venv\Scripts\python.exe scripts\ingest_resumes.py --folder "C:\path\to\new_resumes"

The script will:
- Parse each supported file using the project's parser helpers
- Use the filename (without extension) as `name` when not available
- Append new rows to `data/resumes.csv` with unique numeric `candidate_id`

Be careful: this edits `data/resumes.csv`. A backup will be written as `data/resumes.csv.bak`.
"""
import argparse
import os
import sys
import pandas as pd
from pathlib import Path

# Add project src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.parser import parse_pdf_resume, parse_docx_resume


SUPPORTED_TEXT = ('.txt',)
SUPPORTED_PDF = ('.pdf',)
SUPPORTED_DOCX = ('.docx',)
SUPPORTED_CSV = ('.csv',)


def read_text_file(path: Path) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        # try latin-1 fallback
        with open(path, 'r', encoding='latin-1') as f:
            return f.read()


def infer_name_from_filename(path: Path) -> str:
    # Use filename (without extension), replace underscores/dashes with spaces
    return path.stem.replace('_', ' ').replace('-', ' ').title()


def ensure_resumes_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        # create empty DataFrame with required columns
        df = pd.DataFrame(columns=['candidate_id', 'name', 'resume_text'])
        df.to_csv(path, index=False)
        return df
    else:
        return pd.read_csv(path)


def main(folder: str):
    folder_path = Path(folder).expanduser().resolve()
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Folder not found: {folder}")
        return

    data_csv = Path('data') / 'resumes.csv'
    data_csv_backup = data_csv.with_suffix('.csv.bak')

    # Ensure data folder exists
    data_csv.parent.mkdir(parents=True, exist_ok=True)

    # Load existing resumes (or create)
    df = ensure_resumes_csv(data_csv)

    # Backup
    df.to_csv(data_csv_backup, index=False)
    print(f"Backup written to {data_csv_backup}")

    # Determine next candidate_id (numeric)
    if 'candidate_id' in df.columns and not df.empty:
        try:
            max_id = pd.to_numeric(df['candidate_id'], errors='coerce').dropna().astype(int).max()
            next_id = int(max_id) + 1
        except Exception:
            next_id = 1
    else:
        next_id = 1

    added = []

    for file in sorted(folder_path.iterdir()):
        if file.suffix.lower() in SUPPORTED_PDF:
            try:
                text = parse_pdf_resume(str(file))
            except Exception as e:
                print(f"Failed to parse PDF {file.name}: {e}")
                continue
            name = infer_name_from_filename(file)
        elif file.suffix.lower() in SUPPORTED_DOCX:
            try:
                text = parse_docx_resume(str(file))
            except Exception as e:
                print(f"Failed to parse DOCX {file.name}: {e}")
                continue
            name = infer_name_from_filename(file)
        elif file.suffix.lower() in SUPPORTED_TEXT:
            try:
                text = read_text_file(file)
            except Exception as e:
                print(f"Failed to read text file {file.name}: {e}")
                continue
            name = infer_name_from_filename(file)
        elif file.suffix.lower() in SUPPORTED_CSV:
            # If a CSV is provided, we expect it to have required columns
            try:
                new_df = pd.read_csv(file)
            except Exception as e:
                print(f"Failed to read CSV {file.name}: {e}")
                continue
            # Validate columns
            required = {'candidate_id', 'name', 'resume_text'}
            if required.issubset(set(new_df.columns)):
                # Append rows, but ensure candidate_id uniqueness by reassigning ids
                for _, row in new_df.iterrows():
                    df = df.append({
                        'candidate_id': next_id,
                        'name': row.get('name', infer_name_from_filename(file)),
                        'resume_text': row.get('resume_text', '')
                    }, ignore_index=True)
                    added.append((next_id, row.get('name', infer_name_from_filename(file))))
                    next_id += 1
                continue
            else:
                print(f"CSV {file.name} missing required columns {required}. Skipping.")
                continue
        else:
            # unsupported file type
            continue

        # Clean up text length and append
        if not text or not text.strip():
            print(f"No text extracted from {file.name}, skipping")
            continue

        df = df.append({
            'candidate_id': next_id,
            'name': name,
            'resume_text': text
        }, ignore_index=True)
        added.append((next_id, name))
        print(f"Added {file.name} as candidate_id={next_id} name='{name}'")
        next_id += 1

    # Save back
    df.to_csv(data_csv, index=False)
    print(f"Done. Total new resumes added: {len(added)}")
    if added:
        print("Added candidates:")
        for cid, name in added:
            print(f" - {cid}: {name}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Ingest resumes into data/resumes.csv')
    parser.add_argument('--folder', '-f', required=True, help='Folder containing resume files (pdf/docx/txt/csv)')
    args = parser.parse_args()
    main(args.folder)

"""
Standalone script to re-migrate CSV resumes with correct column mapping.
This fixes the empty resume_text issue for CSV-migrated resumes.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import uuid
from src.skill_extractor import SkillExtractor
from src.firebase_client import resumes_collection
from src.parser import clean_text
from firebase_admin import firestore

def main():
    print("=" * 70)
    print("🔧 CSV RESUME RE-MIGRATION TOOL")
    print("=" * 70)
    
    # Load CSV file
    csv_path = 'data/resumes.csv'
    print(f"\n📂 Step 1: Loading CSV from {csv_path}...")
    df_csv = pd.read_csv(csv_path)
    print(f"✓ Loaded {len(df_csv)} resumes from CSV")
    print(f"   Columns: {list(df_csv.columns)}")
    
    # Delete old CSV-migrated resumes
    print(f"\n🗑️  Step 2: Deleting old CSV-migrated resumes...")
    delete_count = 0
    old_docs = resumes_collection.where('source_file', '==', 'migrated_from_csv').stream()
    for doc in old_docs:
        doc.reference.delete()
        delete_count += 1
        print(f"   Deleted: {doc.id}")
    print(f"✓ Deleted {delete_count} old CSV resumes")
    
    # Initialize skill extractor
    print(f"\n🔧 Step 3: Initializing skill extractor...")
    extractor = SkillExtractor(skills_dict_path='data/skills_dictionary.txt')
    print("✓ Skill extractor ready")
    
    # Re-migrate with skill extraction
    print(f"\n📦 Step 4: Re-migrating {len(df_csv)} resumes with skill extraction...")
    print("-" * 70)
    
    success_count = 0
    skip_count = 0
    
    for idx, row in df_csv.iterrows():
        doc_id = f"Candidate_{str(uuid.uuid4())[:8]}"
        
        # Get resume text (CORRECT column names)
        resume_text = row.get('resume_text', '')  # Was 'Resume_str' - now correct!
        candidate_name = row.get('name', f'Unknown_{doc_id}')  # Was 'Category' - now correct!
        
        if not resume_text or len(resume_text.strip()) < 20:
            print(f"⚠️  [{idx+1}/{len(df_csv)}] Skipping {candidate_name} - no resume text")
            skip_count += 1
            continue
        
        # Extract skills and metadata
        resume_text_clean = clean_text(resume_text)
        extracted_data = extractor.extract_all_data(resume_text)
        
        # Create document with extracted data
        resume_doc = {
            'candidate_id': doc_id,
            'name': candidate_name,
            'resume_text': resume_text,
            'skills': extracted_data.get('skills', []),
            'experience_years': extracted_data.get('experience', {}),
            'education': extracted_data.get('education', []),
            'certifications': extracted_data.get('certifications', []),
            'source_file': 'migrated_from_csv',
            'uploaded_at': firestore.SERVER_TIMESTAMP
        }
        
        # Save to Firestore
        resumes_collection.document(doc_id).set(resume_doc)
        
        skills_count = len(extracted_data.get('skills', []))
        print(f"✅ [{idx+1}/{len(df_csv)}] {candidate_name}: {skills_count} skills extracted")
        success_count += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("🎉 RE-MIGRATION COMPLETE!")
    print("=" * 70)
    print(f"✅ Successfully migrated: {success_count} resumes")
    print(f"⚠️  Skipped: {skip_count} resumes")
    print(f"🗑️  Deleted old entries: {delete_count}")
    print("\n💡 Next step: Restart your Streamlit app and click 'Refresh Stats'")
    print("=" * 70)

if __name__ == "__main__":
    main()

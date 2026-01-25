"""
Script to re-migrate CSV resumes with correct column mapping and extract skills.
Run this once to fix the empty skills issue.
"""
import pandas as pd
import uuid
from src.skill_extractor import SkillExtractor
from src.firebase_client import resumes_collection, get_all_resumes
from src.parser import clean_text
import firebase_admin
from firebase_admin import firestore

def fix_csv_resume_migration():
    """Delete old CSV migrations and re-migrate with proper data + skill extraction."""
    
    print("🔧 Starting CSV resume re-migration with skill extraction...")
    
    # Load CSV file with correct columns
    csv_path = 'data/resumes.csv'
    print(f"📂 Loading CSV from {csv_path}...")
    df_csv = pd.read_csv(csv_path)
    print(f"✓ Loaded {len(df_csv)} resumes from CSV")
    print(f"   Columns: {list(df_csv.columns)}")
    
    # Load current Firestore data
    print("\n📥 Fetching resumes from Firestore...")
    df_firestore = get_all_resumes()
    print(f"✓ Loaded {len(df_firestore)} resumes from Firestore")
    
    # Find and delete old CSV-migrated resumes
    csv_resumes = df_firestore[df_firestore['source_file'] == 'migrated_from_csv']
    print(f"\n�️  Found {len(csv_resumes)} old CSV-migrated resumes to delete...")
    
    delete_count = 0
    for idx, row in csv_resumes.iterrows():
        resumes_collection.document(row['candidate_id']).delete()
        delete_count += 1
    print(f"✓ Deleted {delete_count} old CSV resumes")
    
    # Initialize skill extractor
    print("\n🔧 Initializing skill extractor...")
    extractor = SkillExtractor(skills_dict_path='data/skills_dictionary.txt')
    
    # Re-migrate with skill extraction
    print(f"\n📦 Re-migrating {len(df_csv)} resumes with skill extraction...")
    success_count = 0
    
    for idx, row in df_csv.iterrows():
        doc_id = str(uuid.uuid4())
        
        # Get resume text (correct column name)
        resume_text = row.get('resume_text', '')
        candidate_name = row.get('name', f'Candidate_{doc_id[:8]}')
        
        if not resume_text or len(resume_text.strip()) < 20:
            print(f"⚠️  Skipping {candidate_name} - no resume text")
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
        print(f"✅ {candidate_name}: {skills_count} skills extracted")
        success_count += 1
    
    print(f"\n🎉 Re-migration complete!")
    print(f"   ✅ Successfully migrated: {success_count} resumes")
    print(f"   🗑️  Deleted old entries: {delete_count}")
    print(f"\n💡 Refresh the Streamlit app (click 'Refresh Stats') to see updated data!")


if __name__ == "__main__":
    fix_csv_resume_migration()

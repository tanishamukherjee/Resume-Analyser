"""
Complete fix script: Delete old CSV migrations and re-migrate with correct columns + skill extraction.
Run this with: streamlit run fix_and_remigrate.py
"""
import streamlit as st
import pandas as pd
import uuid
from src.skill_extractor import SkillExtractor
from src.firebase_client import resumes_collection
from src.parser import clean_text
from firebase_admin import firestore

st.title("🔧 CSV Resume Re-Migration Tool")

if st.button("🚀 Start Re-Migration"):
    with st.spinner("Processing..."):
        # Load CSV file
        csv_path = 'data/resumes.csv'
        st.info(f"📂 Loading CSV from {csv_path}...")
        df_csv = pd.read_csv(csv_path)
        st.success(f"✓ Loaded {len(df_csv)} resumes from CSV")
        st.write(f"   Columns: {list(df_csv.columns)}")
        
        # Delete old CSV-migrated resumes
        st.info("🗑️ Deleting old CSV-migrated resumes...")
        delete_count = 0
        old_docs = resumes_collection.where('source_file', '==', 'migrated_from_csv').get()
        for doc in old_docs:
            doc.reference.delete()
            delete_count += 1
        st.success(f"✓ Deleted {delete_count} old CSV resumes")
        
        # Initialize skill extractor
        st.info("🔧 Initializing skill extractor...")
        extractor = SkillExtractor(skills_dict_path='data/skills_dictionary.txt')
        
        # Re-migrate with skill extraction
        st.info(f"📦 Re-migrating {len(df_csv)} resumes with skill extraction...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        success_count = 0
        
        for idx, row in df_csv.iterrows():
            doc_id = str(uuid.uuid4())
            
            # Get resume text (CORRECT column names)
            resume_text = row.get('resume_text', '')  # Changed from 'Resume_str'
            candidate_name = row.get('name', f'Candidate_{doc_id[:8]}')  # Changed from 'Category'
            
            if not resume_text or len(resume_text.strip()) < 20:
                status_text.warning(f"⚠️ Skipping {candidate_name} - no resume text")
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
            status_text.text(f"✅ {candidate_name}: {skills_count} skills extracted")
            success_count += 1
            
            # Update progress
            progress_bar.progress((idx + 1) / len(df_csv))
        
        st.success(f"""
        🎉 Re-migration complete!
        - ✅ Successfully migrated: {success_count} resumes
        - 🗑️ Deleted old entries: {delete_count}
        """)
        
        st.info("💡 Now restart the main Streamlit app and click 'Refresh Stats' to see all the skills!")

st.markdown("---")
st.markdown("""
### What this does:
1. Loads CSV file (`data/resumes.csv`) with correct column names: `candidate_id`, `name`, `resume_text`
2. Deletes all old CSV-migrated resumes (the ones with empty resume_text)
3. Re-imports all 25 CSV resumes with proper data
4. Extracts skills from each resume during import
5. Saves everything back to Firestore

**After running this, you'll have all 41 resumes (25 CSV + 16 PDF) with proper skills!**
""")

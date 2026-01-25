"""
Firebase Firestore client for resume database operations.
Handles all communication with Firebase Firestore.
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import uuid
from typing import Dict, List
from datetime import datetime

# Initialize Firebase (only once)
if not firebase_admin._apps:
    try:
        # Load credentials from Streamlit secrets
        creds_dict = dict(st.secrets["firebase"])
        creds = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(creds)
        print("✓ Firebase initialized successfully")
    except Exception as e:
        print(f"⚠ Firebase initialization failed: {e}")
        print("Make sure .streamlit/secrets.toml is properly configured")
        # In production, you might want to fall back to a local file
        # creds = credentials.Certificate("path/to/serviceAccountKey.json")
        # firebase_admin.initialize_app(creds)

# Get Firestore client
db = firestore.client()
resumes_collection = db.collection('resumes')
feedback_collection = db.collection('feedback')
search_history_collection = db.collection('search_history')  # New collection for search analytics


@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_all_resumes() -> pd.DataFrame:
    """
    Fetches all resumes from Firestore and returns as a DataFrame.
    Results are cached for 10 minutes to improve performance.
    Includes uploaded_at timestamp for analytics.
    """
    print("📥 Fetching all resumes from Firestore...")
    try:
        docs = resumes_collection.stream()
        resume_list = []
        
        for doc in docs:
            data = doc.to_dict()
            data['candidate_id'] = doc.id  # Use Firestore doc ID as candidate_id
            
            # Convert Firestore Timestamp to datetime for analytics
            if 'uploaded_at' in data and hasattr(data['uploaded_at'], 'timestamp'):
                data['uploaded_at'] = datetime.fromtimestamp(data['uploaded_at'].timestamp())
            elif 'uploaded_at' not in data:
                data['uploaded_at'] = datetime.now()  # Default for older records
            
            resume_list.append(data)
        
        if not resume_list:
            print("⚠ No resumes found in Firestore database")
            return pd.DataFrame(columns=['candidate_id', 'name', 'resume_text', 'uploaded_at'])
        
        df = pd.DataFrame(resume_list)
        print(f"✓ Loaded {len(df)} resumes from Firestore")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching resumes from Firestore: {e}")
        return pd.DataFrame(columns=['candidate_id', 'name', 'resume_text', 'uploaded_at'])


def add_resume(file_name: str, resume_text: str, extracted_data: dict) -> tuple:
    """
    Adds a new resume document to Firestore.
    Checks for duplicates based on resume text hash.
    
    Args:
        file_name: Name of the uploaded file
        resume_text: Full text content of the resume
        extracted_data: Dictionary containing skills, experience, education, etc.
    
    Returns:
        Tuple of (Document ID, candidate name, is_duplicate)
    """
    try:
        # Create a simple hash of the resume text to check for duplicates
        import hashlib
        resume_hash = hashlib.md5(resume_text.encode()).hexdigest()
        
        # Check if this resume already exists using the new filter syntax
        existing_docs = resumes_collection.where(filter=firestore.FieldFilter('resume_hash', '==', resume_hash)).limit(1).stream()
        for doc in existing_docs:
            existing_data = doc.to_dict()
            print(f"⚠ Duplicate detected: {existing_data.get('name', 'Unknown')} (hash: {resume_hash[:8]}...)")
            return (doc.id, existing_data.get('name', 'Duplicate'), True)
        
        # If not a duplicate, add new resume
        doc_id = str(uuid.uuid4())  # Generate a unique ID
        
        # Combine all data into one document
        resume_document = {
            'name': extracted_data.get('name', file_name.replace('.pdf', '').replace('.docx', '').replace('.txt', '')),
            'resume_text': resume_text,
            'resume_hash': resume_hash,
            'skills': extracted_data.get('skills', []),
            'experience_years': extracted_data.get('experience', {}),
            'education': extracted_data.get('education', []),
            'certifications': extracted_data.get('certifications', []),
            'source_file': file_name,
            'uploaded_at': firestore.SERVER_TIMESTAMP
        }
        
        resumes_collection.document(doc_id).set(resume_document)
        print(f"✓ Added resume {doc_id} to Firestore: {resume_document['name']}")
        return (doc_id, resume_document['name'], False)
        
    except Exception as e:
        print(f"❌ Error adding resume to Firestore: {e}")
        raise


def add_feedback(candidate_id: str, job_description: str, feedback: str):
    """
    Adds recruiter feedback to Firestore.
    
    Args:
        candidate_id: ID of the candidate being rated
        job_description: The job description used for matching
        feedback: 'good' or 'bad'
    """
    try:
        feedback_doc = {
            'candidate_id': candidate_id,
            'job_description': job_description[:500],  # Truncate to save space
            'feedback': feedback,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        feedback_collection.add(feedback_doc)
        print(f"✓ Added feedback for {candidate_id}: {feedback}")
        
    except Exception as e:
        print(f"❌ Error adding feedback: {e}")


def migrate_csv_to_firestore(csv_path: str) -> int:
    """
    One-time migration: Import resumes from CSV to Firestore.
    
    Args:
        csv_path: Path to the resumes.csv file
    
    Returns:
        Number of resumes migrated
    """
    try:
        df = pd.read_csv(csv_path)
        count = 0
        
        print(f"📦 Migrating {len(df)} resumes from CSV to Firestore...")
        
        for _, row in df.iterrows():
            doc_id = str(uuid.uuid4())
            resume_doc = {
                'candidate_id': row.get('ID', doc_id),
                'name': row.get('Category', f'Candidate_{doc_id[:8]}'),
                'resume_text': row.get('Resume_str', ''),
                'skills': [],  # Will be extracted later
                'experience_years': {},
                'education': [],
                'certifications': [],
                'source_file': 'migrated_from_csv',
                'uploaded_at': firestore.SERVER_TIMESTAMP
            }
            
            resumes_collection.document(doc_id).set(resume_doc)
            count += 1
            
            if count % 10 == 0:
                print(f"  ... migrated {count} resumes")
        
        print(f"✓ Successfully migrated {count} resumes to Firestore")
        return count
        
    except Exception as e:
        print(f"❌ Error during CSV migration: {e}")
        return 0


def get_feedback_stats() -> Dict:
    """
    Get statistics about recruiter feedback.
    
    Returns:
        Dictionary with feedback counts
    """
    try:
        feedback_docs = feedback_collection.stream()
        good_count = 0
        bad_count = 0
        
        for doc in feedback_docs:
            data = doc.to_dict()
            if data.get('feedback') == 'good':
                good_count += 1
            elif data.get('feedback') == 'bad':
                bad_count += 1
        
        return {
            'good_matches': good_count,
            'bad_matches': bad_count,
            'total_feedback': good_count + bad_count
        }
        
    except Exception as e:
        print(f"❌ Error getting feedback stats: {e}")
        return {'good_matches': 0, 'bad_matches': 0, 'total_feedback': 0}


def update_resume_skills(doc_id: str, skills: list, experience: dict = None, education: list = None, certifications: list = None):
    """
    Update extracted skills and metadata for an existing resume in Firestore.
    
    Args:
        doc_id: Document ID of the resume to update
        skills: List of extracted skills
        experience: Dictionary of years of experience per skill
        education: List of education entries
        certifications: List of certifications
    """
    try:
        update_data = {'skills': skills}
        
        if experience is not None:
            update_data['experience_years'] = experience
        if education is not None:
            update_data['education'] = education
        if certifications is not None:
            update_data['certifications'] = certifications
        
        resumes_collection.document(doc_id).update(update_data)
        print(f"✓ Updated skills for resume {doc_id[:12]}...")
        
    except Exception as e:
        print(f"❌ Error updating resume skills: {e}")


def save_job_search(job_description: str, matching_candidates_count: int) -> None:
    """
    Save job search data to Firestore for analytics.
    
    Args:
        job_description: The job description text that was searched
        matching_candidates_count: Number of matching candidates found
    """
    try:
        search_doc = {
            'job_description': job_description,
            'matching_candidates_count': matching_candidates_count,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        
        search_history_collection.add(search_doc)
        print(f"✓ Saved search to history: {matching_candidates_count} matches")
        
    except Exception as e:
        print(f"❌ Error saving search history: {e}")


@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_search_history() -> pd.DataFrame:
    """
    Fetch all job search history from Firestore.
    Results are cached for 30 minutes.
    
    Returns:
        DataFrame with columns: search_id, job_description, timestamp, matching_candidates_count
    """
    try:
        docs = search_history_collection.stream()
        search_list = []
        
        for doc in docs:
            data = doc.to_dict()
            data['search_id'] = doc.id
            
            # Convert Firestore Timestamp to datetime
            if 'timestamp' in data and hasattr(data['timestamp'], 'timestamp'):
                data['timestamp'] = datetime.fromtimestamp(data['timestamp'].timestamp())
            elif 'timestamp' not in data:
                data['timestamp'] = datetime.now()
            
            search_list.append(data)
        
        if not search_list:
            print("⚠ No search history found")
            return pd.DataFrame(columns=['search_id', 'job_description', 'timestamp', 'matching_candidates_count'])
        
        df = pd.DataFrame(search_list)
        print(f"✓ Loaded {len(df)} search records from history")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching search history: {e}")
        return pd.DataFrame(columns=['search_id', 'job_description', 'timestamp', 'matching_candidates_count'])

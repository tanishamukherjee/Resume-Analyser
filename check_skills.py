"""Quick script to check skills status"""
from src.firebase_client import get_all_resumes
import pandas as pd

# Get all resumes
df = get_all_resumes()

print("=" * 70)
print("SKILLS STATUS REPORT")
print("=" * 70)

# Overall stats
print(f"\nTotal resumes: {len(df)}")

# By source
csv_resumes = df[df['source_file'] == 'migrated_from_csv']
uploaded_resumes = df[df['source_file'] != 'migrated_from_csv']

print(f"CSV resumes: {len(csv_resumes)}")
print(f"Uploaded resumes: {len(uploaded_resumes)}")

# Skills count
csv_with_skills = csv_resumes[csv_resumes['skills'].apply(lambda x: len(x) > 0 if isinstance(x, list) else False)]
csv_without_skills = csv_resumes[csv_resumes['skills'].apply(lambda x: len(x) == 0 if isinstance(x, list) else True)]

uploaded_with_skills = uploaded_resumes[uploaded_resumes['skills'].apply(lambda x: len(x) > 0 if isinstance(x, list) else False)]

print(f"\nCSV resumes WITH skills: {len(csv_with_skills)}")
print(f"CSV resumes WITHOUT skills: {len(csv_without_skills)}")
print(f"Uploaded resumes with skills: {len(uploaded_with_skills)}")

# Unique skills
all_skills = set()
for skills in df['skills']:
    if isinstance(skills, list):
        all_skills.update(skills)

print(f"\nTotal unique skills: {len(all_skills)}")

# Sample CSV resumes
print("\n" + "=" * 70)
print("SAMPLE CSV RESUMES:")
print("=" * 70)
for idx, row in csv_resumes.head(5).iterrows():
    skills_count = len(row['skills']) if isinstance(row['skills'], list) else 0
    has_text = len(row.get('resume_text', '')) > 20
    print(f"\n{row['name']}:")
    print(f"  Skills count: {skills_count}")
    print(f"  Has resume text: {has_text}")
    if skills_count > 0:
        print(f"  Sample skills: {row['skills'][:5]}")

"""
One-time migration script: Import resumes from CSV to Firebase Firestore.
Run this once to migrate your existing data to the cloud database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.firebase_client import migrate_csv_to_firestore

def main():
    """Main migration function."""
    print("=" * 60)
    print("  Resume Database Migration: CSV → Firebase Firestore")
    print("=" * 60)
    print()
    
    csv_path = input("Enter path to resumes.csv [default: data/resumes.csv]: ").strip()
    if not csv_path:
        csv_path = "data/resumes.csv"
    
    print(f"\n📂 Using CSV file: {csv_path}")
    print()
    
    confirm = input("⚠️  This will upload all resumes to Firestore. Continue? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("❌ Migration cancelled.")
        return
    
    print("\n🚀 Starting migration...")
    print("-" * 60)
    
    try:
        count = migrate_csv_to_firestore(csv_path)
        print("-" * 60)
        print(f"\n✅ Migration complete! Successfully migrated {count} resumes to Firestore.")
        print()
        print("Next steps:")
        print("1. Run the new app: streamlit run app_firebase.py")
        print("2. The resumes will be loaded from Firestore automatically")
        print("3. Skills will be extracted on first load (may take a minute)")
        print()
    
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nPlease check:")
        print("- Firebase credentials in .streamlit/secrets.toml")
        print("- CSV file path is correct")
        print("- Internet connection is active")

if __name__ == "__main__":
    main()

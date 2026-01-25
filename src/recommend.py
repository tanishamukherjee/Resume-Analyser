#!/usr/bin/env python3
"""
CLI tool for resume recommendation.
Run this script to test the recommender on sample data.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.recommender import ResumeRecommender


def main():
    """Main CLI entry point."""
    print("=" * 60)
    print("Resume Recommender System - CLI Demo")
    print("=" * 60)
    
    # Initialize recommender
    recommender = ResumeRecommender(skills_dict_path='data/skills_dictionary.txt')
    
    # Load resumes
    print("\n[1/3] Loading resumes...")
    recommender.load_resumes('data/resumes.csv')
    
    # Build index
    print("\n[2/3] Building search index...")
    recommender.build_index(use_annoy=False)
    
    # Show statistics
    stats = recommender.get_stats()
    print(f"\n📊 Dataset Statistics:")
    print(f"   - Total candidates: {stats['n_candidates']}")
    print(f"   - Unique skills: {stats['n_unique_skills']}")
    print(f"   - Avg skills per candidate: {stats['avg_skills_per_candidate']:.1f}")
    print(f"\n   Top 5 skills:")
    for skill, count in list(stats['top_skills'].items())[:5]:
        print(f"      • {skill}: {count}")
    
    # Sample job descriptions to test
    job_examples = [
        {
            "title": "Senior Python Developer",
            "description": """
            We are seeking a Senior Python Developer with expertise in machine learning
            and cloud deployment. Must have experience with AWS, Docker, and ML frameworks
            like TensorFlow or scikit-learn. Django or Flask experience is a plus.
            """
        },
        {
            "title": "DevOps Engineer",
            "description": """
            Looking for a DevOps Engineer skilled in Kubernetes, Docker, and CI/CD pipelines.
            Experience with AWS or Azure, Terraform, and monitoring tools required.
            Python or Bash scripting skills preferred.
            """
        },
        {
            "title": "Frontend Developer",
            "description": """
            Frontend Developer needed with strong React and TypeScript skills.
            Experience with modern web development, responsive design, and testing
            frameworks like Jest or Cypress. Knowledge of Vue or Angular is a bonus.
            """
        }
    ]
    
    # Test each job
    print("\n" + "=" * 60)
    print("[3/3] Testing Recommendations")
    print("=" * 60)
    
    for job in job_examples:
        print(f"\n🔍 Job Opening: {job['title']}")
        print("-" * 60)
        
        # Get recommendations
        results = recommender.recommend(
            job_description=job['description'],
            top_k=5,
            min_similarity=0.0
        )
        
        print(f"\n✨ Top {len(results)} Recommended Candidates:\n")
        
        for i, candidate in enumerate(results, 1):
            print(f"{i}. {candidate['name']} (ID: {candidate['candidate_id']})")
            print(f"   Similarity Score: {candidate['score']:.3f}")
            print(f"   Matching Skills: {', '.join(candidate['common_skills'][:8])}")
            if len(candidate['common_skills']) > 8:
                print(f"   ... and {len(candidate['common_skills']) - 8} more")
            print()
    
    # Interactive mode
    print("\n" + "=" * 60)
    print("💡 Tip: Launch the Streamlit demo for interactive exploration:")
    print("   streamlit run app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()

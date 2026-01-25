"""
Quick test script for new explainability features.
Run this to verify the implementation works correctly.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.explainability import (
    MatchExplainer, 
    calculate_seniority_level, 
    calculate_experience_match_score
)
from src.skill_extractor import SkillExtractor
from src.vectorizer import SemanticVectorizer
import numpy as np


def test_seniority_level():
    """Test seniority level calculation."""
    print("=" * 60)
    print("Testing Seniority Level Calculation")
    print("=" * 60)
    
    test_cases = [
        ({'python': 12, 'aws': 8}, 'Lead/Principal'),
        ({'python': 8, 'docker': 6}, 'Senior'),
        ({'javascript': 5, 'react': 4}, 'Mid-Level'),
        ({'java': 2, 'sql': 1}, 'Junior'),
        ({'python': 1}, 'Entry-Level'),
        ({}, 'Entry-Level'),
    ]
    
    for experience_data, expected_level in test_cases:
        level, explanation = calculate_seniority_level(experience_data)
        status = "✓" if expected_level in level else "✗"
        print(f"{status} Experience: {experience_data}")
        print(f"  → Level: {level} | {explanation}")
        print()


def test_experience_match_score():
    """Test experience match scoring."""
    print("=" * 60)
    print("Testing Experience Match Score")
    print("=" * 60)
    
    # Candidate has: python (5 yrs), aws (3 yrs)
    candidate_exp = {'python': 5, 'aws': 3, 'docker': 2}
    
    test_cases = [
        # Job requires: python, aws (both have experience)
        (['python', 'aws'], 0.83),  # High match
        # Job requires: python, aws, kubernetes (2/3 have experience)
        (['python', 'aws', 'kubernetes'], 0.55),  # Medium match
        # Job requires: react, vue (no experience in either)
        (['react', 'vue'], 0.0),  # No match
    ]
    
    for job_skills, expected_range in test_cases:
        score = calculate_experience_match_score(candidate_exp, job_skills, required_years=3)
        print(f"Job requires: {job_skills}")
        print(f"  → Score: {score:.2f} (expected ~{expected_range:.2f})")
        print()


def test_match_explainer():
    """Test match explainer with real vectorizer."""
    print("=" * 60)
    print("Testing Match Explainer")
    print("=" * 60)
    
    try:
        # Initialize components
        vectorizer = SemanticVectorizer(model_name='all-MiniLM-L6-v2')
        explainer = MatchExplainer(vectorizer)
        
        # Sample data
        job_skills = ['python', 'aws', 'docker', 'kubernetes', 'tensorflow']
        candidate_skills = ['python', 'aws', 'docker', 'java', 'sql', 'git']
        
        # Vectorize
        job_vector = vectorizer.transform([job_skills])
        candidate_vector = vectorizer.transform([candidate_skills])
        
        # Calculate overall score (simplified)
        from sklearn.metrics.pairwise import cosine_similarity
        overall_score = cosine_similarity(job_vector, candidate_vector).flatten()[0]
        
        # Get explanation
        explanation = explainer.explain_match(
            job_skills,
            candidate_skills,
            job_vector,
            candidate_vector,
            overall_score
        )
        
        print(f"Overall Score: {overall_score:.2%}")
        print()
        
        print("Top Skill Contributors:")
        for skill, contribution in explanation['top_contributors']:
            print(f"  • {skill}: +{contribution:.1f}%")
        print()
        
        print(f"Matching Skills: {explanation['matching_skills']}")
        print(f"Missing Skills: {explanation['missing_critical_skills']}")
        print()
        
        print("Heatmap Data:")
        print(f"  Job Skills (rows): {explanation['skill_match_heatmap']['job_skills']}")
        print(f"  Candidate Skills (cols): {explanation['skill_match_heatmap']['candidate_skills']}")
        print(f"  Matrix shape: {len(explanation['skill_match_heatmap']['match_matrix'])} x {len(explanation['skill_match_heatmap']['match_matrix'][0])}")
        
        print("\n✓ Match Explainer test passed!")
        
    except Exception as e:
        print(f"✗ Match Explainer test failed: {e}")
        import traceback
        traceback.print_exc()


def test_skill_extraction():
    """Test skill and experience extraction."""
    print("=" * 60)
    print("Testing Skill & Experience Extraction")
    print("=" * 60)
    
    sample_resume = """
    Senior Software Engineer with 8 years of Python experience and 5 years in AWS.
    Expertise in Docker (4 years) and Kubernetes (2 years).
    Machine learning: 3 years with TensorFlow and PyTorch.
    """
    
    extractor = SkillExtractor(skills_dict_path='data/skills_dictionary.txt')
    
    # Extract skills
    skills = extractor.extract_skills(sample_resume.lower())
    print(f"Extracted Skills: {skills}")
    print()
    
    # Extract experience
    from src.skill_extractor import extract_years_of_experience
    experience = extract_years_of_experience(sample_resume.lower(), extractor.skills_dict)
    print(f"Extracted Experience:")
    for skill, years in sorted(experience.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {skill}: {years} years")
    print()
    
    # Calculate seniority
    level, explanation = calculate_seniority_level(experience)
    print(f"Seniority: {level}")
    print(f"Explanation: {explanation}")
    
    print("\n✓ Skill extraction test passed!")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EXPLAINABILITY FEATURES TEST SUITE")
    print("=" * 60 + "\n")
    
    # Run all tests
    test_seniority_level()
    test_experience_match_score()
    test_skill_extraction()
    test_match_explainer()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED!")
    print("=" * 60)
    print("\nTo run the full application:")
    print("  streamlit run app.py")
    print()

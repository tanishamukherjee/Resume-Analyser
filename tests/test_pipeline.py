"""
Unit tests for the resume recommender pipeline.
Run: pytest tests/
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import clean_text
from src.skill_extractor import (
    SkillExtractor,
    extract_years_of_experience,
    extract_education,
    extract_certifications
)
from src.vectorizer import SkillVectorizer, BinarySkillVectorizer


def test_clean_text():
    """Test text cleaning."""
    raw = "  Python Developer\n\n  with 5+ years!  "
    cleaned = clean_text(raw)
    assert "python developer" in cleaned
    assert "\n" not in cleaned


def test_skill_extraction():
    """Test skill extraction from resume text."""
    extractor = SkillExtractor()
    
    text = """
    senior software engineer with python, javascript, and aws experience.
    skilled in machine learning, docker, and react.js
    """
    
    skills = extractor.extract_skills(text)
    
    # Check core skills are extracted
    assert 'python' in skills
    assert 'javascript' in skills
    assert 'aws' in skills
    assert 'docker' in skills
    
    # Check normalization
    if 'react.js' in text:
        # Should be normalized to 'react'
        assert 'react' in skills or 'react.js' in skills


def test_skill_vectorization():
    """Test skill vectorization."""
    skill_lists = [
        ['python', 'machine learning', 'aws'],
        ['java', 'spring boot', 'aws'],
        ['python', 'django', 'postgresql']
    ]
    
    vectorizer = SkillVectorizer()
    vectors = vectorizer.fit_transform(skill_lists)
    
    assert vectors.shape[0] == 3  # 3 candidates
    assert vectors.shape[1] > 0   # At least some features
    
    # Test transform on new data
    new_skills = [['python', 'aws']]
    new_vectors = vectorizer.transform(new_skills)
    assert new_vectors.shape[0] == 1


def test_binary_vectorization():
    """Test binary skill vectorization."""
    skill_lists = [
        ['python', 'java'],
        ['python', 'javascript'],
        ['java', 'c++']
    ]
    
    vectorizer = BinarySkillVectorizer()
    vectors = vectorizer.fit_transform(skill_lists)
    
    assert vectors.shape[0] == 3
    assert vectors.shape[1] == 4  # 4 unique skills
    assert vectors.sum() == 6      # 6 total skill occurrences


def test_skill_weights():
    """Test applying skill weights."""
    skill_lists = [
        ['python', 'java', 'aws'],
        ['javascript', 'react', 'node.js']
    ]
    
    vectorizer = SkillVectorizer()
    vectors = vectorizer.fit_transform(skill_lists)
    
    # Apply weights
    weights = {'python': 2.0, 'java': 1.5}
    weighted = vectorizer.apply_skill_weights(vectors, weights)
    
    assert weighted.shape == vectors.shape


def test_synonym_normalization():
    """Test skill synonym mapping."""
    extractor = SkillExtractor()
    
    text = "expert in react.js, node.js, and kubernetes (k8s)"
    skills = extractor.extract_skills(text)
    
    # Check synonyms are normalized
    assert 'react' in skills or 'react.js' in skills
    assert 'node.js' in skills
    assert 'kubernetes' in skills


def test_extract_years_of_experience():
    """Test extraction of years of experience from resume text."""
    
    # Test case 1: Standard format
    text1 = """
    Senior Software Engineer with 5+ years of Python experience.
    3 years experience in AWS cloud services.
    Java (4 years)
    """
    result1 = extract_years_of_experience(text1.lower())
    assert 'python' in result1
    assert result1['python'] == 5
    assert 'aws' in result1
    assert result1['aws'] == 3
    assert 'java' in result1
    assert result1['java'] == 4
    
    # Test case 2: Colon format
    text2 = """
    Skills:
    - Python: 6 years
    - Machine Learning: 2 years
    - Docker - 3 years
    """
    result2 = extract_years_of_experience(text2.lower())
    assert result2.get('python') == 6
    assert result2.get('machine learning') == 2
    assert result2.get('docker') == 3
    
    # Test case 3: Experience phrase
    text3 = """
    5+ years React experience
    3 years Node.js experience
    """
    result3 = extract_years_of_experience(text3.lower())
    assert result3.get('react') == 5
    assert result3.get('node.js') == 3
    
    print("✓ Years of experience extraction test passed")


def test_extract_education_and_certs():
    """Test extraction of education and certifications from resume text."""
    
    # Test education extraction
    edu_text1 = """
    Education:
    - B.S. in Computer Science from MIT (2015)
    - M.S. in Machine Learning from Stanford (2017)
    """
    edu_result1 = extract_education(edu_text1.lower())
    assert 'B.S.' in edu_result1
    assert 'M.S.' in edu_result1
    
    edu_text2 = """
    PhD in Artificial Intelligence
    Bachelor of Engineering in Electronics
    """
    edu_result2 = extract_education(edu_text2.lower())
    assert 'Ph.D.' in edu_result2
    assert 'B.Eng.' in edu_result2
    
    # Test certifications extraction
    cert_text1 = """
    Certifications:
    - AWS Certified Solutions Architect
    - Google Cloud Professional
    - PMP Certified
    """
    cert_result1 = extract_certifications(cert_text1.lower())
    assert 'AWS Certified' in cert_result1
    assert 'Google Cloud Certified' in cert_result1
    assert 'PMP' in cert_result1
    
    cert_text2 = """
    Certified Scrum Master (CSM)
    CISSP - Certified Information Systems Security Professional
    CompTIA Security+ certified
    """
    cert_result2 = extract_certifications(cert_text2.lower())
    assert 'Scrum Master' in cert_result2
    assert 'CISSP' in cert_result2
    assert 'CompTIA Security+' in cert_result2
    
    print("✓ Education and certifications extraction test passed")


def test_full_profile_extraction():
    """Test complete profile extraction using SkillExtractor."""
    
    extractor = SkillExtractor()
    
    resume_text = """
    John Doe
    Senior Software Engineer
    
    Experience:
    5+ years of Python development
    3 years experience in AWS
    Machine Learning: 2 years
    
    Education:
    M.S. in Computer Science - Stanford University
    B.S. in Software Engineering - MIT
    
    Certifications:
    - AWS Certified Solutions Architect
    - PMP Certified
    
    Skills: Python, Java, Docker, Kubernetes, TensorFlow, React
    """
    
    profile = extractor.extract_full_profile(resume_text.lower())
    
    # Check skills
    assert 'python' in profile['skills']
    assert 'aws' in profile['skills']
    
    # Check experience
    assert profile['experience'].get('python') == 5
    assert profile['experience'].get('aws') == 3
    assert profile['experience'].get('machine learning') == 2
    
    # Check education
    assert 'M.S.' in profile['education']
    assert 'B.S.' in profile['education']
    
    # Check certifications
    assert 'AWS Certified' in profile['certifications']
    assert 'PMP' in profile['certifications']
    
    print("✓ Full profile extraction test passed")


if __name__ == "__main__":
    print("Running tests...")
    
    test_clean_text()
    print("✓ Text cleaning test passed")
    
    test_skill_extraction()
    print("✓ Skill extraction test passed")
    
    test_skill_vectorization()
    print("✓ Skill vectorization test passed")
    
    test_binary_vectorization()
    print("✓ Binary vectorization test passed")
    
    test_skill_weights()
    print("✓ Skill weights test passed")
    
    test_synonym_normalization()
    print("✓ Synonym normalization test passed")
    
    test_extract_years_of_experience()
    
    test_extract_education_and_certs()
    
    test_full_profile_extraction()
    
    print("\n✅ All tests passed!")

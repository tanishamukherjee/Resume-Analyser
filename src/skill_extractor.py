"""
Skill extraction and normalization module.
Extracts technical skills from resume text using dictionary matching and pattern rules.
Also extracts years of experience, education, and certifications.
"""
import re
from typing import List, Set, Dict

# Import SpaCy for advanced NLP
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: SpaCy not available. Install with: pip install spacy")


class SkillExtractor:
    """Extract and normalize skills from resume text with SpaCy enhancement."""
    
    def __init__(self, skills_dict_path: str = None):
        """
        Initialize skill extractor.
        
        Args:
            skills_dict_path: Path to skills dictionary file (one skill per line)
        """
        self.skills_dict = self._load_skills_dictionary(skills_dict_path)
        self.skill_synonyms = self._build_synonym_map()
        
        # Load SpaCy model for entity recognition
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("SpaCy model loaded successfully")
            except OSError:
                print("Warning: SpaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
                self.nlp = None
        else:
            self.nlp = None
    
    def _load_skills_dictionary(self, filepath: str) -> Set[str]:
        """Load skills from dictionary file."""
        if filepath is None:
            filepath = 'data/skills_dictionary.txt'
        
        skills = set()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        skills.add(line)
        except FileNotFoundError:
            print(f"Warning: Skills dictionary not found at {filepath}")
            # Fallback to basic skills
            skills = {'python', 'java', 'javascript', 'sql', 'aws', 'docker'}
        
        return skills
    
    def _build_synonym_map(self) -> Dict[str, str]:
        """Build a map of skill synonyms to canonical forms."""
        synonyms = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'ml': 'machine learning',
            'ai': 'artificial intelligence',
            'dl': 'deep learning',
            'k8s': 'kubernetes',
            'react.js': 'react',
            'node': 'node.js',
            'reactjs': 'react',
            'nodejs': 'node.js',
            'vue.js': 'vue',
            'vuejs': 'vue',
            'angular.js': 'angular',
            'angularjs': 'angular',
            'postgres': 'postgresql',
            'mongo': 'mongodb',
            'tf': 'tensorflow',
            'sklearn': 'scikit-learn',
            'cv': 'computer vision',
            'nlp': 'natural language processing',
        }
        return synonyms
    
    def extract_skills(self, text: str) -> List[str]:
        """
        Extract skills from text using dictionary matching + SpaCy entity recognition.
        
        Args:
            text: Resume text (should be cleaned/lowercased)
        
        Returns:
            List of extracted skills (normalized)
        """
        if not text:
            return []
        
        text = text.lower()
        found_skills = []
        
        # Method 1: Dictionary matching
        for skill in self.skills_dict:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text):
                found_skills.append(skill)
        
        # Method 2: Pattern-based extraction for common formats
        # e.g., "Python 3.9", "AWS Cloud", "React.js"
        patterns = [
            r'\b(python|java|javascript|typescript|c\+\+|c#|golang|ruby|php)\s*\d*\.?\d*\b',
            r'\b(aws|azure|gcp)\s+(cloud|services?|platform)?\b',
            r'\b(react|angular|vue|node)\.?js\b',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                skill = match.lower().strip()
                if skill and skill not in found_skills:
                    found_skills.append(skill)
        
        # Method 3: SpaCy entity recognition for organizations/products
        if self.nlp is not None:
            try:
                doc = self.nlp(text[:10000])  # Limit to first 10k chars for performance
                for ent in doc.ents:
                    # Extract organizations and products as potential skills
                    if ent.label_ in ['ORG', 'PRODUCT']:
                        entity_text = ent.text.lower().strip()
                        # Filter out common non-skill entities
                        excluded_terms = ['company', 'inc', 'llc', 'corporation', 'corp', 'ltd', 'university', 'college']
                        if (entity_text not in found_skills and 
                            len(entity_text) > 2 and 
                            not any(exc in entity_text for exc in excluded_terms)):
                            found_skills.append(entity_text)
            except Exception as e:
                print(f"Warning: SpaCy processing error: {e}")
        
        # Normalize using synonym map
        normalized = []
        for skill in found_skills:
            normalized_skill = self.skill_synonyms.get(skill, skill)
            if normalized_skill not in normalized:
                normalized.append(normalized_skill)
        
        return sorted(set(normalized))
    
    def extract_skills_batch(self, texts: List[str]) -> List[List[str]]:
        """Extract skills from multiple texts."""
        return [self.extract_skills(text) for text in texts]
    
    def extract_full_profile(self, text: str) -> Dict:
        """
        Extract complete profile from resume text including skills, experience, education, and certifications.
        
        Args:
            text: Resume text (cleaned/lowercased)
        
        Returns:
            Dict with keys: 'skills', 'experience', 'education', 'certifications'
        """
        return {
            'skills': self.extract_skills(text),
            'experience': extract_years_of_experience(text, self.skills_dict),
            'education': extract_education(text),
            'certifications': extract_certifications(text)
        }
    
    def extract_all_data(self, text: str) -> Dict:
        """
        Extract all relevant data points from resume text.
        This is an alias for extract_full_profile with added name extraction.
        
        Args:
            text: Resume text (original case preserved for name extraction)
        
        Returns:
            Dict with keys: 'name', 'skills', 'experience', 'education', 'certifications'
        """
        clean_text = text.lower()
        
        return {
            'name': self.extract_name(text),  # Use original text for name
            'skills': self.extract_skills(clean_text),
            'experience': extract_years_of_experience(clean_text, self.skills_dict),
            'education': extract_education(clean_text),
            'certifications': extract_certifications(clean_text)
        }
    
    def extract_name(self, text: str) -> str:
        """
        Extract a candidate's name using SpaCy NER.
        
        Args:
            text: Resume text (original case)
        
        Returns:
            Extracted name or "Unknown"
        """
        if not text:
            return "Unknown"
        
        # Try SpaCy first
        if self.nlp is not None:
            try:
                # Look at first 500 chars (name usually at top)
                doc = self.nlp(text[:500])
                for ent in doc.ents:
                    if ent.label_ == 'PERSON':
                        return ent.text.strip()
            except Exception as e:
                print(f"Warning: SpaCy name extraction error: {e}")
        
        # Fallback: assume name is on the first non-empty line
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            # Skip short lines, lines with email, phone numbers, URLs
            if (len(line) > 3 and 
                '@' not in line and 
                not re.search(r'\d{3}', line) and  # Has 3+ digits
                not line.startswith('http') and
                len(line) < 50):  # Not too long
                return line
        
        return "Unknown"
    
    def extract_profiles_batch(self, texts: List[str]) -> List[Dict]:
        """Extract complete profiles from multiple texts."""
        return [self.extract_full_profile(text) for text in texts]


def extract_years_of_experience(text: str, skills_dict: Set[str] = None) -> Dict[str, int]:
    """
    Extract years of experience for various skills from resume text.
    
    Args:
        text: Resume text (should be cleaned/lowercased)
        skills_dict: Optional set of skills to look for (from skills dictionary)
    
    Returns:
        Dict mapping skill name to years of experience, e.g., {'python': 5, 'aws': 3}
    
    Examples:
        - "5+ years of Python"
        - "3 years experience in AWS"
        - "Java (4 years)"
        - "Machine Learning: 2 years"
    """
    if not text:
        return {}
    
    text = text.lower()
    experience_data = {}
    
    # Common patterns for years of experience
    # Match skill names (allow dots only within, not at end)
    # Allow 1-2 word skills (e.g., "python", "machine learning")
    skill_pattern = r'[a-z][a-z0-9\-\+\#]*(?:\.[a-z0-9\-\+\#]+)*'
    skill_single = skill_pattern
    skill_double = skill_pattern + r'\s+' + skill_pattern
    
    patterns = [
        # "Python: 5 years", "Machine Learning: 2 years"  
        rf'({skill_double})\s*:\s*(\d+)\+?\s*years?',
        rf'({skill_single})\s*:\s*(\d+)\+?\s*years?',
        # "Python - 5 years", "Docker - 3 years"
        rf'({skill_double})\s+\-\s+(\d+)\+?\s*years?',
        rf'({skill_single})\s+\-\s+(\d+)\+?\s*years?',
        # "Python (5 years)", "Deep Learning (6 months)"
        rf'({skill_double})\s*\((\d+)\+?\s*(?:years?|months?)\)',
        rf'({skill_single})\s*\((\d+)\+?\s*(?:years?|months?)\)',
        # "5+ years of Python", "5 years in Machine Learning" (with prepositions)
        rf'(\d+)\+?\s*years?\s+(?:of\s+|in\s+|with\s+|experience\s+(?:in\s+|with\s+))({skill_single})',
        # "5+ years Python experience" (without preposition, but followed by "experience")
        rf'(\d+)\+?\s*years?\s+({skill_single})\s+(?:experience|exp)(?:\s|$|\.|\,)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) == 2:
                # Determine which group is the number and which is the skill
                if match[0].isdigit():
                    years_str, skill = match[0], match[1].strip()
                else:
                    skill, years_str = match[0].strip(), match[1]
                
                # Convert to years (handle both years and months)
                years = int(years_str)
                # Check if "months" appears near the number in original text
                if 'month' in text[max(0, text.find(str(years_str))-20):text.find(str(years_str))+20]:
                    years = max(1, years // 12)  # Convert months to years, minimum 1
                
                # Clean up skill name: remove punctuation, normalize whitespace
                skill = skill.lower().strip()
                skill = re.sub(r'[^\w\s\-\.\+\#]', '', skill)  # Remove non-alphanumeric except -,.+#
                skill = re.sub(r'\s+', ' ', skill).strip()  # Normalize whitespace
                
                # Remove trailing common words
                skill = re.sub(r'\s+(experience|exp|developer|engineer|programming)$', '', skill).strip()
                
                # Remove leading prepositions/articles
                skill = re.sub(r'^(of|in|with|the|a|an)\s+', '', skill).strip()
                
                # Skip empty or common non-skill words
                common_words = ['experience', 'exp', 'developer', 'engineer', 'programming', 'years', 'months', 
                                'of', 'in', 'with', 'the', 'a', 'an']
                if not skill or skill in common_words:
                    continue
                
                # Filter by skills_dict if provided
                if skills_dict is None or skill in skills_dict or any(s in skill for s in skills_dict):
                    # Keep the maximum years if skill mentioned multiple times
                    if skill not in experience_data or years > experience_data[skill]:
                        experience_data[skill] = years
    
    return experience_data


def extract_education(text: str) -> List[str]:
    """
    Extract education degrees from resume text.
    
    Args:
        text: Resume text (should be cleaned/lowercased)
    
    Returns:
        List of found degrees, e.g., ['B.S.', 'M.S.', 'Ph.D.']
    
    Examples:
        - "B.S. in Computer Science"
        - "Master of Science"
        - "PhD in Machine Learning"
    """
    if not text:
        return []
    
    text = text.lower()
    education_list = []
    
    # Common degree patterns
    patterns = [
        r'\b(ph\.?d\.?|doctorate|doctoral degree)\b',
        r'\b(m\.?s\.?|m\.?sc\.?|master of science|masters in)\b',
        r'\b(m\.?b\.?a\.?|master of business administration)\b',
        r'\b(m\.?eng\.?|master of engineering)\b',
        r'\b(b\.?s\.?|b\.?sc\.?|bachelor of science|bachelors in)\b',
        r'\b(b\.?a\.?|bachelor of arts)\b',
        r'\b(b\.?eng\.?|b\.?tech\.?|bachelor of engineering|bachelor of technology)\b',
        r'\b(associate degree|associates in|a\.?s\.?)\b',
    ]
    
    degree_mapping = {
        'ph.d': 'Ph.D.',
        'phd': 'Ph.D.',
        'doctorate': 'Ph.D.',
        'doctoral degree': 'Ph.D.',
        'm.s': 'M.S.',
        'ms': 'M.S.',
        'm.sc': 'M.S.',
        'msc': 'M.S.',
        'master of science': 'M.S.',
        'masters in': 'M.S.',
        'm.b.a': 'M.B.A.',
        'mba': 'M.B.A.',
        'master of business administration': 'M.B.A.',
        'm.eng': 'M.Eng.',
        'meng': 'M.Eng.',
        'master of engineering': 'M.Eng.',
        'b.s': 'B.S.',
        'bs': 'B.S.',
        'b.sc': 'B.S.',
        'bsc': 'B.S.',
        'bachelor of science': 'B.S.',
        'bachelors in': 'B.S.',
        'b.a': 'B.A.',
        'ba': 'B.A.',
        'bachelor of arts': 'B.A.',
        'b.eng': 'B.Eng.',
        'beng': 'B.Eng.',
        'b.tech': 'B.Tech.',
        'btech': 'B.Tech.',
        'bachelor of engineering': 'B.Eng.',
        'bachelor of technology': 'B.Tech.',
        'associate degree': 'Associate',
        'associates in': 'Associate',
        'a.s': 'Associate',
        'as': 'Associate',
    }
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            degree = match.strip().lower().replace('.', '').replace(' ', '')
            # Map to standardized form
            for key, value in degree_mapping.items():
                if degree in key.replace('.', '').replace(' ', ''):
                    if value not in education_list:
                        education_list.append(value)
                    break
    
    return sorted(set(education_list))


def extract_certifications(text: str) -> List[str]:
    """
    Extract certifications from resume text.
    
    Args:
        text: Resume text (should be cleaned/lowercased)
    
    Returns:
        List of found certifications, e.g., ['AWS Certified', 'PMP']
    
    Examples:
        - "AWS Certified Solutions Architect"
        - "PMP Certified"
        - "Google Cloud Professional"
    """
    if not text:
        return []
    
    text = text.lower()
    certifications_list = []
    
    # Common certification patterns
    certification_patterns = {
        'AWS Certified': r'\b(aws certified|aws certification|aws professional)\b',
        'Azure Certified': r'\b(azure certified|microsoft certified azure|azure certification|azure professional)\b',
        'Google Cloud Certified': r'\b(google cloud certified|gcp certified|google cloud certification|google cloud professional|gcp professional)\b',
        'PMP': r'\b(pmp|project management professional)\b',
        'CISSP': r'\b(cissp|certified information systems security professional)\b',
        'CompTIA Security+': r'\b(comptia security\+|security\+ certified)\b',
        'CompTIA A+': r'\b(comptia a\+|a\+ certified)\b',
        'Certified Kubernetes': r'\b(ck[ad]|certified kubernetes administrator|certified kubernetes application developer)\b',
        'Scrum Master': r'\b(csm|certified scrum master|scrum master certified)\b',
        'Six Sigma': r'\b(six sigma|lean six sigma)\b',
        'ITIL': r'\b(itil certified|itil foundation)\b',
        'Salesforce Certified': r'\b(salesforce certified|salesforce certification)\b',
        'Oracle Certified': r'\b(oracle certified|oca|ocp)\b',
        'Red Hat Certified': r'\b(red hat certified|rhcsa|rhce)\b',
    }
    
    for cert_name, pattern in certification_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            if cert_name not in certifications_list:
                certifications_list.append(cert_name)
    
    return sorted(certifications_list)


if __name__ == "__main__":
    # Test skill extraction
    extractor = SkillExtractor()
    
    sample_resume = """
    Senior Software Engineer with 5+ years of experience.
    Proficient in Python, JavaScript, and Java.
    Expertise in AWS cloud services, Docker, and Kubernetes (k8s).
    Strong background in machine learning (ML) and data analysis using pandas.
    Experience with React.js, Node.js, and MongoDB.
    """
    
    skills = extractor.extract_skills(sample_resume.lower())
    print(f"Extracted skills: {skills}")

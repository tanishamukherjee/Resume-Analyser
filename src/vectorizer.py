"""
Vectorization module.
Converts extracted skills into numerical vectors using TF-IDF or BERT embeddings.
"""
from typing import List, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

# Import SentenceTransformers for semantic embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not available. Install with: pip install sentence-transformers")


class SkillVectorizer:
    """Convert skill lists to TF-IDF vectors."""
    
    def __init__(self):
        self.vectorizer = None
        self.feature_names = None
    
    def fit_transform(self, skill_lists: List[List[str]]) -> np.ndarray:
        """
        Fit vectorizer and transform skills to vectors.
        
        Args:
            skill_lists: List of skill lists (one per candidate)
        
        Returns:
            TF-IDF matrix (n_candidates x n_skills)
        """
        # Convert skill lists to space-separated strings
        skill_documents = [' '.join(skills) for skills in skill_lists]
        
        # Use TF-IDF with word-level tokenization
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r'\b[\w\-\.]+\b',  # Handle multi-word skills
            max_features=500,  # Limit vocabulary size
            min_df=1,  # Minimum document frequency
            sublinear_tf=True  # Use log scaling for term frequency
        )
        
        vectors = self.vectorizer.fit_transform(skill_documents)
        self.feature_names = self.vectorizer.get_feature_names_out()
        
        return vectors
    
    def transform(self, skill_lists: List[List[str]]) -> np.ndarray:
        """
        Transform new skill lists using fitted vectorizer.
        
        Args:
            skill_lists: List of skill lists to transform
        
        Returns:
            TF-IDF vectors
        """
        if self.vectorizer is None:
            raise ValueError("Vectorizer not fitted. Call fit_transform first.")
        
        skill_documents = [' '.join(skills) for skills in skill_lists]
        return self.vectorizer.transform(skill_documents)
    
    def get_feature_names(self) -> List[str]:
        """Get the skill vocabulary."""
        return list(self.feature_names) if self.feature_names is not None else []
    
    def apply_skill_weights(
        self, 
        vectors: np.ndarray, 
        skill_weights: Dict[str, float]
    ) -> np.ndarray:
        """
        Apply custom weights to specific skills.
        
        Args:
            vectors: TF-IDF vectors
            skill_weights: Dict mapping skill name to weight multiplier
        
        Returns:
            Weighted vectors
        """
        if self.feature_names is None:
            return vectors
        
        weighted = vectors.toarray() if hasattr(vectors, 'toarray') else vectors.copy()
        
        for skill, weight in skill_weights.items():
            skill_lower = skill.lower()
            if skill_lower in self.feature_names:
                idx = list(self.feature_names).index(skill_lower)
                weighted[:, idx] *= weight
        
        # Renormalize after weighting
        return normalize(weighted, norm='l2')


class BinarySkillVectorizer:
    """Simpler binary vectorizer (skill present or not)."""
    
    def __init__(self):
        self.vocabulary = None
        self.skill_to_idx = None
    
    def fit_transform(self, skill_lists: List[List[str]]) -> np.ndarray:
        """Create binary skill vectors."""
        # Build vocabulary
        all_skills = set()
        for skills in skill_lists:
            all_skills.update(skills)
        
        self.vocabulary = sorted(all_skills)
        self.skill_to_idx = {skill: idx for idx, skill in enumerate(self.vocabulary)}
        
        # Create binary matrix
        vectors = np.zeros((len(skill_lists), len(self.vocabulary)))
        
        for i, skills in enumerate(skill_lists):
            for skill in skills:
                if skill in self.skill_to_idx:
                    vectors[i, self.skill_to_idx[skill]] = 1
        
        return vectors
    
    def transform(self, skill_lists: List[List[str]]) -> np.ndarray:
        """Transform new skill lists to binary vectors."""
        if self.vocabulary is None:
            raise ValueError("Vectorizer not fitted.")
        
        vectors = np.zeros((len(skill_lists), len(self.vocabulary)))
        
        for i, skills in enumerate(skill_lists):
            for skill in skills:
                if skill in self.skill_to_idx:
                    vectors[i, self.skill_to_idx[skill]] = 1
        
        return vectors


class SemanticVectorizer:
    """
    Convert skill lists to semantic vectors using BERT embeddings.
    Uses SentenceTransformers for state-of-the-art semantic similarity.
    """
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the semantic vectorizer.
        
        Args:
            model_name: Name of the SentenceTransformer model to use
                       'all-MiniLM-L6-v2' is fast and efficient (default)
                       'all-mpnet-base-v2' is slower but more accurate
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
        
        print(f"Loading semantic model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.feature_names = None  # Not really used for BERT, but kept for compatibility
        print(f"✓ Semantic model loaded: {model_name}")
    
    def fit_transform(self, skill_lists: List[List[str]]) -> np.ndarray:
        """
        Fit and transform skills to semantic vectors.
        
        Args:
            skill_lists: List of skill lists (one per candidate)
        
        Returns:
            Semantic embedding matrix (n_candidates x embedding_dim)
        """
        # Convert skill lists to natural language sentences
        skill_documents = [' '.join(skills) if skills else 'no skills' for skills in skill_lists]
        
        # Encode to semantic vectors
        print(f"Encoding {len(skill_documents)} skill profiles...")
        vectors = self.model.encode(
            skill_documents, 
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True  # Normalize for cosine similarity
        )
        
        print(f"✓ Encoded to {vectors.shape[1]}-dimensional vectors")
        return vectors
    
    def transform(self, skill_lists: List[List[str]]) -> np.ndarray:
        """
        Transform new skill lists using the model.
        
        Args:
            skill_lists: List of skill lists to transform
        
        Returns:
            Semantic vectors
        """
        skill_documents = [' '.join(skills) if skills else 'no skills' for skills in skill_lists]
        vectors = self.model.encode(
            skill_documents,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return vectors
    
    def get_feature_names(self) -> List[str]:
        """Return empty list for compatibility (BERT doesn't have feature names)."""
        return []
    
    def apply_skill_weights(
        self, 
        vectors: np.ndarray, 
        skill_weights: Dict[str, float]
    ) -> np.ndarray:
        """
        Note: Applying simple weights to semantic vectors is complex.
        For now, we return the original vectors with a warning.
        
        Args:
            vectors: Semantic vectors
            skill_weights: Dict mapping skill name to weight (not used)
        
        Returns:
            Original vectors (unchanged)
        """
        if skill_weights:
            print("⚠ Warning: Skill weights are not applied with SemanticVectorizer.")
            print("  Semantic embeddings already capture skill importance in context.")
        return vectors


class MultiSectionVectorizer:
    """
    Advanced vectorizer that embeds different resume sections separately,
    then aggregates with learned weights.
    
    Sections:
    - Skills (technical competencies)
    - Experience (work history, projects)
    - Education (degrees, certifications)
    
    This captures more nuanced information than single-vector embeddings.
    """
    
    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        weights: Dict[str, float] = None
    ):
        """
        Initialize multi-section vectorizer.
        
        Args:
            model_name: SentenceTransformer model name
            weights: Section weights (default: skills=0.6, experience=0.3, education=0.1)
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers not installed")
        
        self.model = SentenceTransformer(model_name)
        
        # Default weights favor skills, then experience, then education
        self.weights = weights or {
            'skills': 0.6,
            'experience': 0.3,
            'education': 0.1
        }
        
        print(f"✓ Multi-Section Vectorizer initialized")
        print(f"  Section weights: {self.weights}")
    
    def _prepare_section_text(self, section_data, section_type: str) -> str:
        """
        Convert section data to text for embedding.
        
        Args:
            section_data: Skills list, experience dict, or education list
            section_type: 'skills', 'experience', or 'education'
        
        Returns:
            Text representation of the section
        """
        if section_type == 'skills':
            if isinstance(section_data, list):
                return ' '.join(section_data) if section_data else 'no skills'
            return str(section_data) if section_data else 'no skills'
        
        elif section_type == 'experience':
            if isinstance(section_data, dict):
                # Convert experience dict to text
                exp_parts = [f"{skill} {years} years" for skill, years in section_data.items()]
                return ' '.join(exp_parts) if exp_parts else 'no experience listed'
            return str(section_data) if section_data else 'no experience listed'
        
        elif section_type == 'education':
            if isinstance(section_data, list):
                return ' '.join(section_data) if section_data else 'no education listed'
            return str(section_data) if section_data else 'no education listed'
        
        return 'no data'
    
    def fit_transform(
        self,
        skills_lists: List[List[str]],
        experience_lists: List[Dict],
        education_lists: List[List[str]]
    ) -> np.ndarray:
        """
        Embed each resume section separately, then aggregate.
        
        Args:
            skills_lists: List of skill lists per candidate
            experience_lists: List of experience dicts per candidate
            education_lists: List of education lists per candidate
        
        Returns:
            Aggregated embedding vectors (n_candidates x embedding_dim)
        """
        n_candidates = len(skills_lists)
        
        # Embed each section
        print("Encoding skills sections...")
        skills_texts = [self._prepare_section_text(skills, 'skills') for skills in skills_lists]
        skills_embeddings = self.model.encode(skills_texts, convert_to_numpy=True, show_progress_bar=True)
        
        print("Encoding experience sections...")
        exp_texts = [self._prepare_section_text(exp, 'experience') for exp in experience_lists]
        exp_embeddings = self.model.encode(exp_texts, convert_to_numpy=True, show_progress_bar=True)
        
        print("Encoding education sections...")
        edu_texts = [self._prepare_section_text(edu, 'education') for edu in education_lists]
        edu_embeddings = self.model.encode(edu_texts, convert_to_numpy=True, show_progress_bar=True)
        
        # Weighted aggregation
        print("Aggregating section embeddings...")
        aggregated = (
            self.weights['skills'] * skills_embeddings +
            self.weights['experience'] * exp_embeddings +
            self.weights['education'] * edu_embeddings
        )
        
        # Re-normalize after weighted sum
        from sklearn.preprocessing import normalize
        aggregated = normalize(aggregated, norm='l2')
        
        print(f"✓ Multi-section embeddings created: {aggregated.shape}")
        return aggregated
    
    def transform(
        self,
        skills_lists: List[List[str]],
        experience_lists: List[Dict],
        education_lists: List[List[str]]
    ) -> np.ndarray:
        """Transform new candidates using multi-section approach."""
        # Same as fit_transform (no fitting needed for pre-trained model)
        return self.fit_transform(skills_lists, experience_lists, education_lists)
    
    def get_section_embeddings(
        self,
        skills_lists: List[List[str]],
        experience_lists: List[Dict],
        education_lists: List[List[str]]
    ) -> Dict[str, np.ndarray]:
        """
        Get individual section embeddings without aggregation.
        Useful for analysis and debugging.
        
        Returns:
            Dict with keys 'skills', 'experience', 'education'
        """
        skills_texts = [self._prepare_section_text(skills, 'skills') for skills in skills_lists]
        exp_texts = [self._prepare_section_text(exp, 'experience') for exp in experience_lists]
        edu_texts = [self._prepare_section_text(edu, 'education') for edu in education_lists]
        
        return {
            'skills': self.model.encode(skills_texts, convert_to_numpy=True),
            'experience': self.model.encode(exp_texts, convert_to_numpy=True),
            'education': self.model.encode(edu_texts, convert_to_numpy=True)
        }


if __name__ == "__main__":
    # Test vectorization
    sample_skills = [
        ['python', 'machine learning', 'tensorflow', 'aws'],
        ['java', 'spring boot', 'aws', 'docker'],
        ['python', 'django', 'postgresql', 'docker'],
        ['javascript', 'react', 'node.js', 'mongodb']
    ]
    
    # Test TF-IDF vectorizer
    print("=== Testing TF-IDF Vectorizer ===")
    vectorizer = SkillVectorizer()
    vectors = vectorizer.fit_transform(sample_skills)
    print(f"Vector shape: {vectors.shape}")
    print(f"Feature names: {vectorizer.get_feature_names()[:10]}")
    
    # Test Semantic vectorizer
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        print("\n=== Testing Semantic Vectorizer ===")
        semantic_vec = SemanticVectorizer()
        semantic_vectors = semantic_vec.fit_transform(sample_skills)
        print(f"Semantic vector shape: {semantic_vectors.shape}")
        print(f"First vector sample: {semantic_vectors[0][:5]}")
        
        print("\n=== Testing Multi-Section Vectorizer ===")
        sample_experience = [
            {'python': 5, 'aws': 3},
            {'java': 7, 'spring boot': 5},
            {'python': 3, 'django': 2},
            {'javascript': 4, 'react': 3}
        ]
        sample_education = [
            ['M.S.', 'B.S.'],
            ['B.S.'],
            ['Ph.D.', 'M.S.'],
            ['B.S.']
        ]
        
        multi_vec = MultiSectionVectorizer()
        multi_vectors = multi_vec.fit_transform(sample_skills, sample_experience, sample_education)
        print(f"Multi-section vector shape: {multi_vectors.shape}")
        print(f"First vector sample: {multi_vectors[0][:5]}")


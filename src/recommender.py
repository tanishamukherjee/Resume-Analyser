"""
Recommender module.
Implements similarity search and ranking for candidate recommendation.
"""
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
# Annoy is optional; wrap import so the app can run without it.
try:
    from annoy import AnnoyIndex
    _HAS_ANNOY = True
except Exception:  # pragma: no cover - optional dependency
    AnnoyIndex = None
    _HAS_ANNOY = False

from .parser import clean_text
from .skill_extractor import SkillExtractor
from .vectorizer import SkillVectorizer, SemanticVectorizer, MultiSectionVectorizer
from .explainability import (
    MatchExplainer, 
    calculate_seniority_level, 
    calculate_experience_match_score
)
from .skill_classifier import SkillClassifier
from .hybrid_retrieval import HybridRetriever

# Import Firebase client - handle import error gracefully
try:
    from .firebase_client import get_all_resumes, add_resume, save_job_search, get_search_history
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Warning: Firebase client not available")


class ResumeRecommender:
    """Main recommender system for matching candidates to jobs - with Firebase integration."""
    
    def __init__(
        self,
        skills_dict_path: str = None,
        use_semantic: bool = True,
        use_multi_section: bool = False,
        use_hybrid_retrieval: bool = False
    ):
        """
        Initialize recommender.
        
        Args:
            skills_dict_path: Path to skills dictionary file
            use_semantic: If True, use SemanticVectorizer (BERT), else use TF-IDF
            use_multi_section: If True, use MultiSectionVectorizer for separate section embeddings
            use_hybrid_retrieval: If True, use BM25 + BERT hybrid search
        """
        self.extractor = SkillExtractor(skills_dict_path)
        self.skill_classifier = SkillClassifier()
        
        # Choose vectorizer based on flags
        if use_multi_section:
            try:
                self.vectorizer = MultiSectionVectorizer(model_name='all-MiniLM-L6-v2')
                self.use_multi_section = True
                print("✓ Using Multi-Section Vectorizer (skills, experience, education)")
            except ImportError:
                print("⚠ Falling back to standard semantic vectorizer")
                self.vectorizer = SemanticVectorizer(model_name='all-MiniLM-L6-v2')
                self.use_multi_section = False
        elif use_semantic:
            try:
                self.vectorizer = SemanticVectorizer(model_name='all-MiniLM-L6-v2')
                self.use_multi_section = False
                print("✓ Using Semantic (BERT) Vectorizer for matching")
            except ImportError:
                print("⚠ Falling back to TF-IDF vectorizer")
                self.vectorizer = SkillVectorizer()
                self.use_multi_section = False
        else:
            self.vectorizer = SkillVectorizer()
            self.use_multi_section = False
            print("✓ Using TF-IDF Vectorizer for matching")
        
        # Initialize explainer
        self.explainer = MatchExplainer(self.vectorizer)
        
        # Initialize hybrid retriever if requested
        self.use_hybrid_retrieval = use_hybrid_retrieval
        self.hybrid_retriever = None
        if use_hybrid_retrieval:
            self.hybrid_retriever = HybridRetriever(self.vectorizer)
            print("✓ Hybrid Retrieval (BM25 + BERT) enabled")
        
        self.df = None
        self.vectors = None
        self.annoy_index = None
        self.n_trees = 10
    
    def load_resumes(self, filepath: str = None):
        """
        Load resumes from Firestore (or CSV for backward compatibility).
        
        Args:
            filepath: Optional CSV path for backward compatibility (if None, loads from Firestore)
        """
        if filepath is None:
            # Load from Firebase
            if not FIREBASE_AVAILABLE:
                raise ImportError("Firebase client not available. Install firebase-admin or provide a CSV filepath.")
            
            self.df = get_all_resumes()
            
            if self.df.empty:
                print("⚠ No resumes found in Firestore")
                return
            
            # Extract skills if not already in database
            needs_extraction = (
                'skills' not in self.df.columns or 
                self.df['skills'].isna().any() or
                self.df['skills'].apply(lambda x: len(x) == 0 if isinstance(x, list) else True).any()
            )
            
            if needs_extraction:
                print(f"Extracting skills and metadata from {len(self.df)} resumes...")
                self.df['resume_text_clean'] = self.df['resume_text'].apply(clean_text)
                
                profiles = self.extractor.extract_profiles_batch(
                    self.df['resume_text_clean'].tolist()
                )
                
                # Store each component
                self.df['skills'] = [p['skills'] for p in profiles]
                self.df['experience'] = [p.get('experience', {}) for p in profiles]
                self.df['education'] = [p.get('education', []) for p in profiles]
                self.df['certifications'] = [p.get('certifications', []) for p in profiles]
                
                print(f"Extracted complete profiles for {len(self.df)} candidates")
                
                # Update Firebase with extracted skills
                print("Updating Firestore with extracted skills...")
                from .firebase_client import update_resume_skills
                for idx, row in self.df.iterrows():
                    if row['skills']:  # Only update if skills were extracted
                        update_resume_skills(
                            row['candidate_id'],
                            row['skills'],
                            row.get('experience', {}),
                            row.get('education', []),
                            row.get('certifications', [])
                        )
                print("✓ Firestore updated with extracted skills")
            else:
                print(f"Loaded {len(self.df)} candidates from Firestore (skills already extracted)")
        
        else:
            # Legacy CSV loading
            from .parser import load_resumes_from_csv
            self.df = load_resumes_from_csv(filepath)
            
            print(f"Extracting skills and metadata from {len(self.df)} resumes...")
            profiles = self.extractor.extract_profiles_batch(
                self.df['resume_text_clean'].tolist()
            )
            
            self.df['skills'] = [p['skills'] for p in profiles]
            self.df['experience'] = [p['experience'] for p in profiles]
            self.df['education'] = [p['education'] for p in profiles]
            self.df['certifications'] = [p['certifications'] for p in profiles]
            
            print(f"Extracted complete profiles for {len(self.df)} candidates")
    
    def add_new_resume(self, file_object, file_name: str):
        """
        Parse, extract, and save a new resume to Firestore.
        
        Args:
            file_object: File-like object from Streamlit file_uploader
            file_name: Name of the uploaded file
        
        Returns:
            Tuple of (document_id, candidate_name, is_duplicate)
        """
        if not FIREBASE_AVAILABLE:
            raise ImportError("Firebase client not available for adding resumes")
        
        from .parser import parse_resume_file
        import streamlit as st
        
        print(f"📝 Processing new file: {file_name}")
        
        # 1. Parse file to extract text
        resume_text = parse_resume_file(file_object, file_name)
        if not resume_text or len(resume_text.strip()) < 50:
            raise ValueError(f"Could not parse meaningful text from {file_name}")
        
        # 2. Extract all data (skills, experience, education, etc.)
        extracted_data = self.extractor.extract_all_data(resume_text)
        
        # 3. Add to Firebase (returns doc_id, name, is_duplicate)
        doc_id, name, is_duplicate = add_resume(file_name, resume_text, extracted_data)
        
        # 4. Clear Streamlit cache to force reload on next use (only if not duplicate)
        if not is_duplicate:
            st.cache_data.clear()
        
        return doc_id, name, is_duplicate
    
    def build_index(self, use_annoy: bool = False):
        """
        Build vector index for similarity search.
        
        Args:
            use_annoy: Use Annoy for approximate nearest neighbor search
        """
        if self.df is None:
            raise ValueError("No resumes loaded. Call load_resumes first.")
        
        # Vectorize based on vectorizer type
        print("Building skill vectors...")
        
        if self.use_multi_section:
            # Multi-section embedding
            self.vectors = self.vectorizer.fit_transform(
                self.df['skills'].tolist(),
                self.df['experience'].tolist(),
                self.df['education'].tolist()
            )
        else:
            # Standard single-vector embedding
            self.vectors = self.vectorizer.fit_transform(self.df['skills'].tolist())
        
        # Build hybrid retrieval index if enabled
        if self.use_hybrid_retrieval and self.hybrid_retriever:
            print("Building hybrid retrieval index (BM25 + BERT)...")
            self.hybrid_retriever.index_documents(
                self.df['skills'].tolist(),
                self.vectors
            )
        
        # Build Annoy index if requested (optional dependency)
        if use_annoy:
            if not _HAS_ANNOY:
                print("Warning: 'annoy' not installed — continuing without Annoy (exact search will be used).")
            else:
                print("Building Annoy index...")
                n_dims = self.vectors.shape[1]
                self.annoy_index = AnnoyIndex(n_dims, 'angular')  # Angular = cosine

                for i in range(len(self.vectors)):
                    # Handle both sparse (TF-IDF) and dense (BERT) vectors
                    if hasattr(self.vectors[i], 'toarray'):
                        vector = self.vectors[i].toarray().flatten()
                    else:
                        vector = self.vectors[i].flatten()
                    self.annoy_index.add_item(i, vector)

                self.annoy_index.build(self.n_trees)
        
        print("Index built successfully")
    
    def recommend(
        self,
        job_description: str,
        top_k: int = 5,
        skill_weights: Optional[Dict[str, float]] = None,
        min_similarity: float = 0.0,
        use_experience_scoring: bool = True,
        required_years: int = 3,
        use_hard_soft_weighting: bool = True
    ) -> List[Dict]:
        """
        Recommend candidates with advanced ML features:
        - Hybrid retrieval (BM25 + BERT)
        - Hard/soft skill weighting
        - Experience-aware scoring
        - Explainability
        
        Args:
            job_description: Text description of the job
            top_k: Number of recommendations to return
            skill_weights: Optional dict of skill importance weights
            min_similarity: Minimum similarity threshold
            use_experience_scoring: Whether to use experience-aware scoring (default True)
            required_years: Minimum years of experience considered adequate (default 3)
            use_hard_soft_weighting: Apply hard/soft skill classification (default True)
        
        Returns:
            List of dicts with candidate info, scores, and explainability data
        """
        if self.vectors is None:
            raise ValueError("Index not built. Call build_index first.")
        
        # Extract skills from job description
        job_skills = self.extractor.extract_skills(job_description.lower())
        print(f"Job requires skills: {job_skills}")
        
        # Classify hard/soft skills and apply weights
        if use_hard_soft_weighting:
            skill_categories = self.skill_classifier.classify_skills(job_skills)
            hard_skill_weights = self.skill_classifier.get_skill_weights(
                job_skills,
                hard_weight=1.0,
                soft_weight=0.3  # Soft skills as boosters
            )
            print(f"  Hard skills: {len(skill_categories['hard'])}")
            print(f"  Soft skills: {len(skill_categories['soft'])} (weighted 0.3x)")
        else:
            hard_skill_weights = None
        
        # Vectorize job skills (multi-section if enabled)
        if self.use_multi_section:
            # For job description, we don't have experience/education, so use skills only
            job_experience = {}
            job_education = []
            job_vector = self.vectorizer.transform([job_skills], [job_experience], [job_education])
        else:
            job_vector = self.vectorizer.transform([job_skills])
        
        # Use hybrid retrieval if enabled
        if self.use_hybrid_retrieval and self.hybrid_retriever:
            print("Using hybrid retrieval (BM25 + BERT)...")
            # Hybrid search returns (index, score) tuples
            search_results = self.hybrid_retriever.search(
                query_skills=job_skills,
                query_vector=job_vector,
                top_k=top_k * 2,  # Get more for filtering
                return_scores=True
            )
            indices = [idx for idx, _ in search_results]
            # Pre-computed hybrid scores
            hybrid_scores_dict = {idx: score for idx, score in search_results}
            use_hybrid = True
            print(f"Hybrid retrieval returned {len(indices)} candidates")
        else:
            # Standard similarity search
            if self.annoy_index and not skill_weights and not hard_skill_weights:
                # Use Annoy for fast search
                if hasattr(job_vector, 'toarray'):
                    job_vec_flat = job_vector.toarray().flatten()
                else:
                    job_vec_flat = job_vector.flatten()
                
                indices, distances = self.annoy_index.get_nns_by_vector(
                    job_vec_flat, top_k * 2, include_distances=True
                )
                similarities = 1 - (np.array(distances) ** 2) / 2
                use_annoy_scores = True
            else:
                # Exact cosine similarity
                similarities = cosine_similarity(job_vector, self.vectors).flatten()
                indices = np.argsort(similarities)[::-1][:top_k * 2]
                use_annoy_scores = False
            
            use_hybrid = False
        
        # Build results with advanced scoring
        results = []
        for i, idx in enumerate(indices):
            if isinstance(idx, np.ndarray):
                idx = idx.item()
            
            candidate = self.df.iloc[idx]
            
            # Get semantic similarity
            if use_hybrid:
                semantic_similarity = hybrid_scores_dict.get(idx, 0.0)
            elif use_annoy_scores:
                semantic_similarity = similarities[i]
            else:
                semantic_similarity = similarities[idx]
            
            # Calculate skill overlap (with hard/soft weighting)
            candidate_skills = candidate['skills']
            job_skills_set = set(job_skills)
            candidate_skills_set = set(candidate_skills)
            common_skills = candidate_skills_set & job_skills_set
            
            if use_hard_soft_weighting and hard_skill_weights:
                # Weighted overlap considering hard vs soft
                weighted_overlap = sum(
                    hard_skill_weights.get(skill, 1.0)
                    for skill in common_skills
                )
                max_possible = sum(hard_skill_weights.values())
                skill_overlap_score = weighted_overlap / max_possible if max_possible > 0 else 0.0
            else:
                skill_overlap_score = len(common_skills) / len(job_skills_set) if job_skills_set else 0.0
            
            # Calculate experience match score
            experience_data = candidate.get('experience', {})
            experience_match = calculate_experience_match_score(
                experience_data, 
                job_skills, 
                required_years
            ) if use_experience_scoring else 0.0
            
            # Calculate seniority level
            seniority_level, seniority_explanation = calculate_seniority_level(experience_data)
            
            # Combined scoring: 60% semantic + 30% skill overlap + 10% experience
            if use_experience_scoring:
                final_score = (
                    0.6 * semantic_similarity + 
                    0.3 * skill_overlap_score + 
                    0.1 * experience_match
                )
            else:
                final_score = semantic_similarity
            
            if final_score < min_similarity:
                continue
            
            # Get vectorized candidate skills for explanation
            candidate_vector = self.vectors[idx:idx+1]
            if hasattr(candidate_vector, 'toarray'):
                candidate_vector = candidate_vector.toarray()
            
            # Generate explanation
            explanation = self.explainer.explain_match(
                job_skills,
                candidate_skills,
                job_vector,
                candidate_vector,
                final_score
            )
            
            # Classify candidate skills
            if use_hard_soft_weighting:
                candidate_skill_categories = self.skill_classifier.classify_skills(candidate_skills)
            else:
                candidate_skill_categories = {'hard': candidate_skills, 'soft': []}
            
            results.append({
                'candidate_id': candidate['candidate_id'],
                'name': candidate['name'],
                'skills': candidate_skills,
                'hard_skills': candidate_skill_categories['hard'],
                'soft_skills': candidate_skill_categories['soft'],
                'common_skills': list(common_skills),
                'score': float(final_score),
                'semantic_similarity': float(semantic_similarity),
                'skill_overlap_score': float(skill_overlap_score),
                'experience_match_score': float(experience_match),
                'seniority_level': seniority_level,
                'seniority_explanation': seniority_explanation,
                'resume_text': candidate['resume_text'][:200] + '...',
                'full_resume_text': candidate['resume_text'],
                'experience': experience_data,
                'education': candidate.get('education', []),
                'certifications': candidate.get('certifications', []),
                'explanation': explanation,
                'retrieval_method': 'hybrid' if use_hybrid else 'bert'
            })
            
            if len(results) >= top_k:
                break
        
        # Sort by final score
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        
        # Save search to history
        if FIREBASE_AVAILABLE:
            try:
                save_job_search(job_description, len(results))
            except Exception as e:
                print(f"Warning: Could not save search history: {e}")
        
        return results
    
    def get_stats(self) -> Dict:
        """Get statistics about the loaded data."""
        if self.df is None or len(self.df) == 0:
            return {
                'n_candidates': 0,
                'n_unique_skills': 0,
                'avg_skills_per_candidate': 0.0,
                'top_skills': {}
            }
        
        all_skills = []
        for skills in self.df['skills']:
            if isinstance(skills, list):
                all_skills.extend(skills)
        
        # Calculate average, handle empty case
        skill_counts = [len(s) if isinstance(s, list) else 0 for s in self.df['skills']]
        avg_skills = np.mean(skill_counts) if skill_counts else 0.0
        
        return {
            'n_candidates': len(self.df),
            'n_unique_skills': len(set(all_skills)) if all_skills else 0,
            'avg_skills_per_candidate': avg_skills,
            'top_skills': pd.Series(all_skills).value_counts().head(10).to_dict() if all_skills else {}
        }
    
    def get_analytics_data(self) -> Dict:
        """
        Get comprehensive analytics data for dashboards.
        
        Returns:
            Dictionary containing:
                - resume_growth_df: Resume uploads over time
                - top_skills_df: Most common skills
                - data_source_df: Distribution of data sources
                - search_history_df: Job search history
                - searched_skills_df: Most searched skills
                - skill_match_rates_df: Supply vs demand analysis
        """
        analytics = {}
        
        # 1. Resume Growth Over Time
        if self.df is not None and len(self.df) > 0 and 'uploaded_at' in self.df.columns:
            try:
                df_growth = self.df.copy()
                df_growth['upload_date'] = pd.to_datetime(df_growth['uploaded_at']).dt.date
                resume_growth = df_growth.groupby('upload_date').size().reset_index(name='count')
                resume_growth.columns = ['Date', 'Resumes']
                resume_growth = resume_growth.set_index('Date')
                analytics['resume_growth_df'] = resume_growth
            except Exception as e:
                print(f"Warning: Could not generate resume growth data: {e}")
                analytics['resume_growth_df'] = pd.DataFrame(columns=['Date', 'Resumes'])
        else:
            analytics['resume_growth_df'] = pd.DataFrame(columns=['Date', 'Resumes'])
        
        # 2. Top Skills (Top 20)
        if self.df is not None and len(self.df) > 0:
            all_skills = []
            for skills in self.df['skills']:
                if isinstance(skills, list):
                    all_skills.extend(skills)
            
            if all_skills:
                top_skills_series = pd.Series(all_skills).value_counts().head(20)
                analytics['top_skills_df'] = pd.DataFrame({
                    'Skill': top_skills_series.index,
                    'Count': top_skills_series.values
                }).set_index('Skill')
            else:
                analytics['top_skills_df'] = pd.DataFrame(columns=['Skill', 'Count'])
        else:
            analytics['top_skills_df'] = pd.DataFrame(columns=['Skill', 'Count'])
        
        # 3. Data Source Distribution
        if self.df is not None and len(self.df) > 0 and 'source_file' in self.df.columns:
            source_counts = self.df['source_file'].value_counts()
            # Map source names to more readable labels
            source_map = {
                'migrated_from_csv': 'CSV Import',
                'uploaded': 'PDF Upload'
            }
            source_counts.index = source_counts.index.map(lambda x: source_map.get(x, x))
            analytics['data_source_df'] = source_counts.to_frame(name='Count')
        else:
            analytics['data_source_df'] = pd.DataFrame(columns=['Source', 'Count'])
        
        # 4. Search History
        if FIREBASE_AVAILABLE:
            try:
                search_history = get_search_history()
                analytics['search_history_df'] = search_history
            except Exception as e:
                print(f"Warning: Could not fetch search history: {e}")
                analytics['search_history_df'] = pd.DataFrame(columns=['search_id', 'job_description', 'timestamp', 'matching_candidates_count'])
        else:
            analytics['search_history_df'] = pd.DataFrame(columns=['search_id', 'job_description', 'timestamp', 'matching_candidates_count'])
        
        # 5. Most Searched Skills (extracted from job descriptions)
        searched_skills = []
        if not analytics['search_history_df'].empty:
            for job_desc in analytics['search_history_df']['job_description']:
                try:
                    skills = self.extractor.extract_skills(str(job_desc).lower())
                    searched_skills.extend(skills)
                except Exception:
                    continue
        
        if searched_skills:
            searched_skills_series = pd.Series(searched_skills).value_counts().head(20)
            analytics['searched_skills_df'] = pd.DataFrame({
                'Skill': searched_skills_series.index,
                'Searches': searched_skills_series.values
            }).set_index('Skill')
        else:
            analytics['searched_skills_df'] = pd.DataFrame(columns=['Skill', 'Searches'])
        
        # 6. Skill Match Rates (Supply vs Demand)
        skill_match_data = []
        if not analytics['searched_skills_df'].empty and self.df is not None and len(self.df) > 0:
            total_searches = len(analytics['search_history_df'])
            total_resumes = len(self.df)
            
            for skill in analytics['searched_skills_df'].index:
                search_count = analytics['searched_skills_df'].loc[skill, 'Searches']
                
                # Count resumes with this skill
                resumes_with_skill = sum(
                    1 for skills_list in self.df['skills'] 
                    if isinstance(skills_list, list) and skill in skills_list
                )
                
                # Calculate metrics
                demand_rate = (search_count / total_searches) if total_searches > 0 else 0
                supply_rate = (resumes_with_skill / total_resumes) if total_resumes > 0 else 0
                match_rate = (supply_rate / demand_rate) if demand_rate > 0 else 0
                
                skill_match_data.append({
                    'Skill': skill,
                    'Searches': search_count,
                    'Resumes with Skill': resumes_with_skill,
                    'Match Rate': round(match_rate, 2),
                    'Gap': 'Shortage' if match_rate < 1 else 'Sufficient'
                })
            
            analytics['skill_match_rates_df'] = pd.DataFrame(skill_match_data)
            # Sort by Match Rate to highlight talent gaps
            analytics['skill_match_rates_df'] = analytics['skill_match_rates_df'].sort_values('Match Rate')
        else:
            analytics['skill_match_rates_df'] = pd.DataFrame(columns=['Skill', 'Searches', 'Resumes with Skill', 'Match Rate', 'Gap'])
        
        return analytics
    
    def add_resume(self, resume_text: str, name: str, candidate_id: str = None):
        """
        Add a new resume to the recommender system dynamically.
        
        Args:
            resume_text: Full text of the resume
            name: Candidate name
            candidate_id: Optional candidate ID (auto-generated if not provided)
        """
        if self.df is None:
            raise ValueError("No resumes loaded. Call load_resumes first.")
        
        # Auto-generate candidate_id if not provided
        if candidate_id is None:
            max_id = pd.to_numeric(self.df['candidate_id'], errors='coerce').max()
            candidate_id = str(int(max_id) + 1) if not pd.isna(max_id) else '1'
        
        # Clean text
        from .parser import clean_text
        resume_text_clean = clean_text(resume_text)
        
        # Extract profile
        profile = self.extractor.extract_full_profile(resume_text_clean)
        
        # Create new row
        new_row = {
            'candidate_id': candidate_id,
            'name': name,
            'resume_text': resume_text,
            'resume_text_clean': resume_text_clean,
            'skills': profile['skills'],
            'experience': profile['experience'],
            'education': profile['education'],
            'certifications': profile['certifications']
        }
        
        # Append to dataframe
        self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Rebuild index with new resume included
        print(f"Added candidate: {name} (ID: {candidate_id})")
        print("Rebuilding index with new resume...")
        self.build_index(use_annoy=(self.annoy_index is not None))
        print("Index rebuilt successfully")


if __name__ == "__main__":
    # Test recommender
    recommender = ResumeRecommender()
    
    # This would need actual data
    print("Recommender initialized")

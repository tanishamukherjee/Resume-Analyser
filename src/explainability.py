"""
Explainability module for resume matching.
Provides skill-level contribution breakdown and matching analysis.
"""
import numpy as np
from typing import List, Dict, Tuple
from sklearn.metrics.pairwise import cosine_similarity


class MatchExplainer:
    """Explains why a candidate matches a job description with skill-level breakdowns."""
    
    def __init__(self, vectorizer):
        """
        Initialize the explainer.
        
        Args:
            vectorizer: The vectorizer used for transforming skills (SkillVectorizer or SemanticVectorizer)
        """
        self.vectorizer = vectorizer
    
    def explain_match(
        self,
        job_skills: List[str],
        candidate_skills: List[str],
        job_vector: np.ndarray,
        candidate_vector: np.ndarray,
        overall_score: float
    ) -> Dict:
        """
        Explain the match between job and candidate with skill-level contributions.
        
        Args:
            job_skills: List of skills extracted from job description
            candidate_skills: List of skills from candidate resume
            job_vector: Vectorized job skills
            candidate_vector: Vectorized candidate skills
            overall_score: Overall similarity score
        
        Returns:
            Dictionary containing:
                - skill_contributions: Dict mapping skill to contribution percentage
                - missing_critical_skills: List of job skills not in candidate profile
                - matching_skills: List of skills present in both
                - skill_match_heatmap: Dict for visualization
                - top_contributors: Top 5 skills contributing to the match
        """
        # 1. Calculate skill overlap
        job_skills_set = set(job_skills)
        candidate_skills_set = set(candidate_skills)
        
        matching_skills = list(job_skills_set & candidate_skills_set)
        missing_skills = list(job_skills_set - candidate_skills_set)
        
        # 2. Calculate per-skill contribution
        skill_contributions = self._calculate_skill_contributions(
            job_skills,
            candidate_skills,
            matching_skills,
            job_vector,
            candidate_vector,
            overall_score
        )
        
        # 3. Identify top contributors
        sorted_contributions = sorted(
            skill_contributions.items(),
            key=lambda x: x[1],
            reverse=True
        )
        top_contributors = sorted_contributions[:5]
        
        # 4. Build heatmap data structure
        heatmap_data = self._build_heatmap_data(
            job_skills,
            candidate_skills,
            skill_contributions
        )
        
        return {
            'skill_contributions': skill_contributions,
            'missing_critical_skills': missing_skills,
            'matching_skills': matching_skills,
            'skill_match_heatmap': heatmap_data,
            'top_contributors': top_contributors,
            'overall_score': overall_score
        }
    
    def _calculate_skill_contributions(
        self,
        job_skills: List[str],
        candidate_skills: List[str],
        matching_skills: List[str],
        job_vector: np.ndarray,
        candidate_vector: np.ndarray,
        overall_score: float
    ) -> Dict[str, float]:
        """
        Calculate how much each skill contributes to the overall match score.
        
        This uses a simplified SHAP-like approach where we calculate the
        contribution of each matching skill by computing similarities with and without it.
        
        Returns:
            Dict mapping skill name to contribution percentage
        """
        contributions = {}
        
        if not matching_skills:
            # No direct matches - calculate semantic contributions
            # For each candidate skill, calculate its semantic similarity to job skills
            for skill in candidate_skills:
                skill_vector = self.vectorizer.transform([[skill]])
                similarity = cosine_similarity(skill_vector, job_vector).flatten()[0]
                # Normalize to percentage contribution
                contribution_pct = (similarity / max(overall_score, 0.01)) * 100
                contributions[skill] = min(contribution_pct, 100.0)  # Cap at 100%
        else:
            # Direct matches exist - calculate contribution based on presence
            # Simple approach: distribute score proportionally among matching skills
            base_contribution = (overall_score * 100) / len(matching_skills)
            
            for skill in matching_skills:
                # Calculate per-skill similarity
                skill_vector = self.vectorizer.transform([[skill]])
                similarity = cosine_similarity(skill_vector, job_vector).flatten()[0]
                
                # Weight by semantic similarity
                weighted_contribution = base_contribution * (similarity / max(overall_score, 0.01))
                contributions[skill] = min(weighted_contribution, 100.0)
        
        # Normalize contributions to sum to ~100%
        total_contrib = sum(contributions.values())
        if total_contrib > 0:
            normalization_factor = (overall_score * 100) / total_contrib
            contributions = {
                skill: min(score * normalization_factor, 100.0)
                for skill, score in contributions.items()
            }
        
        return contributions
    
    def _build_heatmap_data(
        self,
        job_skills: List[str],
        candidate_skills: List[str],
        skill_contributions: Dict[str, float]
    ) -> Dict:
        """
        Build a heatmap data structure for visualization.
        
        Returns:
            Dict with job_skills, candidate_skills, and match_matrix
        """
        # Limit to top skills for visualization
        top_job_skills = job_skills[:10]
        top_candidate_skills = candidate_skills[:15]
        
        # Create match matrix (1 = match, 0 = no match, 0.5 = partial/semantic)
        match_matrix = []
        for job_skill in top_job_skills:
            row = []
            for cand_skill in top_candidate_skills:
                if job_skill == cand_skill:
                    row.append(1.0)  # Exact match
                elif job_skill in cand_skill or cand_skill in job_skill:
                    row.append(0.5)  # Partial match
                else:
                    row.append(0.0)  # No match
            match_matrix.append(row)
        
        return {
            'job_skills': top_job_skills,
            'candidate_skills': top_candidate_skills,
            'match_matrix': match_matrix
        }
    
    def format_explanation_text(self, explanation: Dict) -> str:
        """
        Format explanation as readable text.
        
        Args:
            explanation: Dict from explain_match()
        
        Returns:
            Formatted explanation string
        """
        lines = []
        lines.append(f"Overall Match Score: {explanation['overall_score']:.1%}\n")
        
        # Top contributors
        if explanation['top_contributors']:
            lines.append("Top Skill Contributions:")
            for skill, contribution in explanation['top_contributors']:
                lines.append(f"  • {skill}: +{contribution:.1f}%")
            lines.append("")
        
        # Missing skills
        if explanation['missing_critical_skills']:
            lines.append("Missing Critical Skills:")
            for skill in explanation['missing_critical_skills'][:10]:
                lines.append(f"  ⚠ {skill}")
            if len(explanation['missing_critical_skills']) > 10:
                lines.append(f"  ... and {len(explanation['missing_critical_skills']) - 10} more")
        
        return "\n".join(lines)


def calculate_seniority_level(experience_data: Dict[str, int]) -> Tuple[str, str]:
    """
    Determine seniority level based on years of experience.
    
    Args:
        experience_data: Dict mapping skill to years (e.g., {'python': 5, 'aws': 3})
    
    Returns:
        Tuple of (seniority_level, explanation)
        - seniority_level: 'Junior', 'Mid-Level', 'Senior', 'Lead/Principal'
        - explanation: Human-readable explanation
    """
    if not experience_data:
        return 'Entry-Level', 'No specific experience mentioned'
    
    # Calculate max and average years
    years_list = list(experience_data.values())
    max_years = max(years_list)
    avg_years = sum(years_list) / len(years_list)
    
    # Determine seniority based on thresholds
    if max_years >= 10:
        level = 'Lead/Principal'
        explanation = f'{max_years}+ years experience in {list(experience_data.keys())[years_list.index(max_years)]}'
    elif max_years >= 7:
        level = 'Senior'
        explanation = f'{max_years} years experience, average {avg_years:.1f} years across skills'
    elif max_years >= 4:
        level = 'Mid-Level'
        explanation = f'{max_years} years experience, average {avg_years:.1f} years across skills'
    elif max_years >= 2:
        level = 'Junior'
        explanation = f'{max_years} years experience'
    else:
        level = 'Entry-Level'
        explanation = f'{max_years} year(s) experience'
    
    return level, explanation


def calculate_experience_match_score(
    candidate_experience: Dict[str, int],
    job_skills: List[str],
    required_years: int = 3
) -> float:
    """
    Calculate experience match score (0-1) based on years of experience in relevant skills.
    
    Args:
        candidate_experience: Dict mapping skill to years
        job_skills: List of skills required for the job
        required_years: Minimum years considered adequate (default 3)
    
    Returns:
        Experience match score between 0 and 1
    """
    if not job_skills:
        return 0.0
    
    if not candidate_experience:
        return 0.0
    
    # Calculate experience score for each job skill
    skill_scores = []
    for skill in job_skills:
        # Check if candidate has experience in this skill
        years = candidate_experience.get(skill, 0)
        
        # Score based on years (sigmoid-like curve)
        # 0 years = 0.0, 3 years = 0.7, 5+ years = 1.0
        if years == 0:
            score = 0.0
        elif years >= required_years + 2:
            score = 1.0
        else:
            # Linear interpolation between 0 and 1
            score = min(years / (required_years + 2), 1.0)
        
        skill_scores.append(score)
    
    # Average score across all job skills
    return sum(skill_scores) / len(skill_scores)

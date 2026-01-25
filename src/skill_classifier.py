"""
Skill classifier for categorizing skills as hard vs soft.
Hard skills: Technical, quantifiable (Python, AWS, etc.)
Soft skills: Interpersonal, leadership (Communication, Teamwork, etc.)
"""
from typing import List, Dict, Tuple, Set


class SkillClassifier:
    """Classifies skills into hard (technical) vs soft (interpersonal) categories."""
    
    def __init__(self):
        """Initialize with predefined hard and soft skill dictionaries."""
        self.hard_skills = self._load_hard_skills()
        self.soft_skills = self._load_soft_skills()
        self.hard_skill_keywords = self._build_hard_skill_keywords()
        self.soft_skill_keywords = self._build_soft_skill_keywords()
    
    def _load_hard_skills(self) -> Set[str]:
        """Load comprehensive list of hard/technical skills."""
        return {
            # Programming Languages
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'golang',
            'rust', 'ruby', 'php', 'swift', 'kotlin', 'scala', 'r', 'matlab',
            
            # Web Technologies
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask',
            'spring', 'spring boot', 'fastapi', 'asp.net', 'html', 'css', 'sass',
            'webpack', 'next.js', 'nuxt.js', 'graphql', 'rest', 'api',
            
            # Cloud & DevOps
            'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'k8s',
            'jenkins', 'gitlab', 'github actions', 'terraform', 'ansible', 'chef',
            'puppet', 'ci/cd', 'devops', 'linux', 'unix', 'bash', 'shell scripting',
            
            # Databases
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'dynamodb', 'cassandra', 'oracle', 'sql server', 'sqlite', 'neo4j',
            
            # Data Science & ML
            'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'keras',
            'scikit-learn', 'pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn',
            'nlp', 'natural language processing', 'computer vision', 'opencv',
            'spark', 'hadoop', 'airflow', 'mlflow', 'data science', 'statistics',
            
            # Tools & Platforms
            'git', 'jira', 'confluence', 'slack', 'vs code', 'jupyter', 'postman',
            'tableau', 'power bi', 'excel', 'kafka', 'rabbitmq', 'nginx', 'apache',
            
            # Testing
            'junit', 'pytest', 'selenium', 'cypress', 'jest', 'mocha', 'testing',
            'unit testing', 'integration testing', 'tdd', 'test automation',
            
            # Mobile
            'ios', 'android', 'react native', 'flutter', 'xamarin',
            
            # Security
            'cybersecurity', 'encryption', 'oauth', 'jwt', 'ssl', 'tls',
            
            # Methodologies (technical)
            'agile', 'scrum', 'kanban', 'microservices', 'rest api', 'soap',
            'design patterns', 'solid', 'oop', 'functional programming',
        }
    
    def _load_soft_skills(self) -> Set[str]:
        """Load comprehensive list of soft skills."""
        return {
            # Leadership
            'leadership', 'team leadership', 'mentoring', 'coaching', 'delegation',
            'strategic thinking', 'decision making', 'vision', 'influence',
            
            # Communication
            'communication', 'verbal communication', 'written communication',
            'presentation', 'public speaking', 'active listening', 'negotiation',
            'persuasion', 'storytelling', 'articulation',
            
            # Collaboration
            'teamwork', 'collaboration', 'cross-functional', 'interpersonal',
            'relationship building', 'networking', 'empathy', 'emotional intelligence',
            
            # Problem Solving
            'problem solving', 'critical thinking', 'analytical thinking',
            'creativity', 'innovation', 'adaptability', 'flexibility',
            
            # Work Ethic
            'time management', 'organization', 'attention to detail', 'multitasking',
            'prioritization', 'self-motivation', 'initiative', 'work ethic',
            'reliability', 'accountability', 'responsibility',
            
            # Project Management
            'project management', 'stakeholder management', 'planning',
            'coordination', 'resource management', 'risk management',
            
            # Personal Traits
            'curiosity', 'learning agility', 'growth mindset', 'resilience',
            'conflict resolution', 'customer service', 'professionalism',
        }
    
    def _build_hard_skill_keywords(self) -> Set[str]:
        """Build keywords that indicate hard skills."""
        return {
            'programming', 'development', 'framework', 'library', 'database',
            'cloud', 'platform', 'tool', 'language', 'software', 'technology',
            'system', 'architecture', 'infrastructure', 'deployment', 'api',
        }
    
    def _build_soft_skill_keywords(self) -> Set[str]:
        """Build keywords that indicate soft skills."""
        return {
            'skills', 'ability', 'management', 'building', 'working',
            'thinking', 'solving', 'resolution', 'service', 'oriented',
        }
    
    def classify_skill(self, skill: str) -> str:
        """
        Classify a single skill as 'hard' or 'soft'.
        
        Args:
            skill: Skill name (lowercase)
        
        Returns:
            'hard' or 'soft'
        """
        skill = skill.lower().strip()
        
        # Direct lookup
        if skill in self.hard_skills:
            return 'hard'
        if skill in self.soft_skills:
            return 'soft'
        
        # Keyword-based classification
        # Check if skill contains hard skill keywords
        for keyword in self.hard_skill_keywords:
            if keyword in skill:
                return 'hard'
        
        # Check if skill contains soft skill keywords (only if not already classified as hard)
        for keyword in self.soft_skill_keywords:
            if keyword in skill:
                return 'soft'
        
        # Default: assume technical/hard skill (since most extracted skills are technical)
        return 'hard'
    
    def classify_skills(self, skills: List[str]) -> Dict[str, List[str]]:
        """
        Classify a list of skills into hard and soft categories.
        
        Args:
            skills: List of skill names
        
        Returns:
            Dict with keys 'hard' and 'soft', each containing list of skills
        """
        categorized = {
            'hard': [],
            'soft': []
        }
        
        for skill in skills:
            category = self.classify_skill(skill)
            categorized[category].append(skill)
        
        return categorized
    
    def get_skill_weights(self, skills: List[str], hard_weight: float = 1.0, soft_weight: float = 0.3) -> Dict[str, float]:
        """
        Get weights for skills based on hard/soft classification.
        Hard skills get full weight, soft skills get reduced weight (booster).
        
        Args:
            skills: List of skill names
            hard_weight: Weight for hard skills (default 1.0)
            soft_weight: Weight for soft skills (default 0.3 = booster, not core)
        
        Returns:
            Dict mapping skill to weight
        """
        weights = {}
        
        for skill in skills:
            category = self.classify_skill(skill)
            weights[skill] = hard_weight if category == 'hard' else soft_weight
        
        return weights
    
    def get_categorized_stats(self, skills: List[str]) -> Dict:
        """
        Get statistics about skill categorization.
        
        Args:
            skills: List of skill names
        
        Returns:
            Dict with counts and percentages
        """
        categorized = self.classify_skills(skills)
        
        total = len(skills)
        hard_count = len(categorized['hard'])
        soft_count = len(categorized['soft'])
        
        return {
            'total_skills': total,
            'hard_skills_count': hard_count,
            'soft_skills_count': soft_count,
            'hard_skills_percentage': (hard_count / total * 100) if total > 0 else 0,
            'soft_skills_percentage': (soft_count / total * 100) if total > 0 else 0,
            'hard_skills': categorized['hard'],
            'soft_skills': categorized['soft']
        }


def add_soft_skills_to_dictionary(skills_dict_path: str = 'data/skills_dictionary.txt'):
    """
    Utility function to add soft skills to the skills dictionary file.
    """
    classifier = SkillClassifier()
    
    try:
        # Read existing skills
        with open(skills_dict_path, 'r', encoding='utf-8') as f:
            existing_skills = set(line.strip().lower() for line in f if line.strip() and not line.startswith('#'))
        
        # Add soft skills
        all_skills = existing_skills | classifier.soft_skills
        
        # Write back sorted
        with open(skills_dict_path, 'w', encoding='utf-8') as f:
            f.write("# Technical Skills Dictionary\n")
            f.write("# Format: one skill per line\n")
            f.write("# Auto-updated with soft skills\n\n")
            
            for skill in sorted(all_skills):
                f.write(f"{skill}\n")
        
        print(f"✓ Added {len(classifier.soft_skills)} soft skills to {skills_dict_path}")
        
    except Exception as e:
        print(f"Error updating skills dictionary: {e}")


if __name__ == "__main__":
    # Test the classifier
    classifier = SkillClassifier()
    
    test_skills = [
        'python', 'leadership', 'aws', 'communication', 'docker',
        'teamwork', 'machine learning', 'problem solving', 'kubernetes'
    ]
    
    print("Skill Classification Test:")
    print("=" * 60)
    
    for skill in test_skills:
        category = classifier.classify_skill(skill)
        print(f"{skill:20} → {category}")
    
    print("\n" + "=" * 60)
    categorized = classifier.classify_skills(test_skills)
    print(f"\nHard Skills ({len(categorized['hard'])}): {categorized['hard']}")
    print(f"Soft Skills ({len(categorized['soft'])}): {categorized['soft']}")
    
    print("\n" + "=" * 60)
    weights = classifier.get_skill_weights(test_skills)
    print("\nSkill Weights (hard=1.0, soft=0.3):")
    for skill, weight in weights.items():
        print(f"  {skill}: {weight}")

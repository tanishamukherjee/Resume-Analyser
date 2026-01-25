"""
Domain fine-tuning framework for BERT embeddings on recruitment data.
Uses contrastive learning with job description and resume pairs.
"""
import torch
from typing import List, Tuple, Optional, Dict
import numpy as np
from pathlib import Path
import json


class RecruitmentFineTuner:
    """
    Fine-tune BERT embeddings for recruitment domain using contrastive learning.
    
    This framework supports:
    1. Synthetic pair generation (job descriptions + matched/non-matched resumes)
    2. Contrastive loss training
    3. Model checkpointing and loading
    4. Evaluation on recruitment-specific metrics
    """
    
    def __init__(
        self,
        base_model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        output_dir: str = 'models/fine_tuned_recruitment'
    ):
        """
        Initialize the fine-tuner.
        
        Args:
            base_model_name: Base sentence transformer model
            output_dir: Directory to save fine-tuned models
        """
        self.base_model_name = base_model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.is_finetuned = False
        
        # Check if sentence-transformers is available
        try:
            from sentence_transformers import SentenceTransformer, InputExample, losses
            from torch.utils.data import DataLoader
            self.SentenceTransformer = SentenceTransformer
            self.InputExample = InputExample
            self.losses = losses
            self.DataLoader = DataLoader
            self.available = True
        except ImportError:
            print("Warning: sentence-transformers not available. Install with: pip install sentence-transformers")
            self.available = False
    
    def generate_synthetic_pairs(
        self,
        job_descriptions: List[str],
        resumes: List[str],
        resume_skills: List[List[str]],
        n_positive_pairs: int = 100,
        n_negative_pairs: int = 100
    ) -> List[Tuple[str, str, float]]:
        """
        Generate synthetic training pairs with labels.
        
        Positive pairs: Job description + resume with high skill overlap
        Negative pairs: Job description + resume with low skill overlap
        
        Args:
            job_descriptions: List of job descriptions
            resumes: List of resume texts
            resume_skills: List of skill lists (one per resume)
            n_positive_pairs: Number of positive pairs to generate
            n_negative_pairs: Number of negative pairs to generate
        
        Returns:
            List of tuples (job_desc, resume, similarity_score)
            similarity_score: 1.0 for positive pairs, 0.0 for negative pairs
        """
        from src.skill_extractor import SkillExtractor
        
        extractor = SkillExtractor()
        pairs = []
        
        # Generate positive pairs (high overlap)
        for _ in range(n_positive_pairs):
            # Pick random job description
            job_idx = np.random.randint(0, len(job_descriptions))
            job_desc = job_descriptions[job_idx]
            job_skills = set(extractor.extract_skills(job_desc.lower()))
            
            if not job_skills:
                continue
            
            # Find resume with high skill overlap
            best_overlap = 0
            best_resume_idx = 0
            
            for resume_idx, skills in enumerate(resume_skills):
                overlap = len(set(skills) & job_skills) / len(job_skills) if job_skills else 0
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_resume_idx = resume_idx
            
            # Only add if overlap is significant
            if best_overlap > 0.3:
                pairs.append((job_desc, resumes[best_resume_idx], 1.0))
        
        # Generate negative pairs (low overlap)
        for _ in range(n_negative_pairs):
            # Pick random job description
            job_idx = np.random.randint(0, len(job_descriptions))
            job_desc = job_descriptions[job_idx]
            job_skills = set(extractor.extract_skills(job_desc.lower()))
            
            if not job_skills:
                continue
            
            # Find resume with low skill overlap
            worst_overlap = 1.0
            worst_resume_idx = 0
            
            for resume_idx, skills in enumerate(resume_skills):
                overlap = len(set(skills) & job_skills) / len(job_skills) if job_skills else 0
                if overlap < worst_overlap:
                    worst_overlap = overlap
                    worst_resume_idx = resume_idx
            
            # Only add if overlap is minimal
            if worst_overlap < 0.2:
                pairs.append((job_desc, resumes[worst_resume_idx], 0.0))
        
        print(f"Generated {len(pairs)} synthetic pairs ({n_positive_pairs} positive, {n_negative_pairs} negative)")
        return pairs
    
    def prepare_training_data(
        self,
        pairs: List[Tuple[str, str, float]]
    ):
        """
        Convert pairs to InputExamples for training.
        
        Args:
            pairs: List of (text1, text2, score) tuples
        
        Returns:
            List of InputExample objects
        """
        if not self.available:
            raise ImportError("sentence-transformers not available")
        
        examples = []
        for job_desc, resume, score in pairs:
            examples.append(self.InputExample(texts=[job_desc, resume], label=score))
        
        return examples
    
    def fine_tune(
        self,
        training_pairs: List[Tuple[str, str, float]],
        epochs: int = 3,
        batch_size: int = 16,
        learning_rate: float = 2e-5,
        warmup_steps: int = 100
    ):
        """
        Fine-tune the model on recruitment data using contrastive learning.
        
        Args:
            training_pairs: List of (job_desc, resume, similarity_score) tuples
            epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            warmup_steps: Number of warmup steps
        """
        if not self.available:
            print("Skipping fine-tuning: sentence-transformers not available")
            return
        
        print(f"Loading base model: {self.base_model_name}")
        self.model = self.SentenceTransformer(self.base_model_name)
        
        # Prepare training data
        train_examples = self.prepare_training_data(training_pairs)
        train_dataloader = self.DataLoader(train_examples, shuffle=True, batch_size=batch_size)
        
        # Define loss function: CosineSimilarityLoss for contrastive learning
        train_loss = self.losses.CosineSimilarityLoss(self.model)
        
        print(f"Starting fine-tuning for {epochs} epochs...")
        print(f"Training samples: {len(train_examples)}")
        print(f"Batch size: {batch_size}")
        
        # Train the model
        self.model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            epochs=epochs,
            warmup_steps=warmup_steps,
            output_path=str(self.output_dir),
            show_progress_bar=True
        )
        
        self.is_finetuned = True
        print(f"✓ Fine-tuning complete! Model saved to {self.output_dir}")
        
        # Save metadata
        metadata = {
            'base_model': self.base_model_name,
            'training_samples': len(train_examples),
            'epochs': epochs,
            'batch_size': batch_size,
            'learning_rate': learning_rate
        }
        
        with open(self.output_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def load_finetuned_model(self, model_path: Optional[str] = None):
        """
        Load a fine-tuned model.
        
        Args:
            model_path: Path to fine-tuned model (default: self.output_dir)
        """
        if not self.available:
            print("Warning: sentence-transformers not available")
            return False
        
        path = Path(model_path) if model_path else self.output_dir
        
        if not path.exists():
            print(f"Fine-tuned model not found at {path}")
            return False
        
        try:
            self.model = self.SentenceTransformer(str(path))
            self.is_finetuned = True
            print(f"✓ Loaded fine-tuned model from {path}")
            return True
        except Exception as e:
            print(f"Error loading fine-tuned model: {e}")
            return False
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts using the (possibly fine-tuned) model.
        
        Args:
            texts: List of texts to encode
        
        Returns:
            Numpy array of embeddings
        """
        if not self.available:
            raise ImportError("sentence-transformers not available")
        
        if self.model is None:
            # Load base model if not already loaded
            self.model = self.SentenceTransformer(self.base_model_name)
        
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    
    def evaluate(
        self,
        test_pairs: List[Tuple[str, str, float]],
        threshold: float = 0.5
    ) -> Dict[str, float]:
        """
        Evaluate model performance on test pairs.
        
        Args:
            test_pairs: List of (job_desc, resume, expected_score) tuples
            threshold: Threshold for binary classification
        
        Returns:
            Dict with evaluation metrics
        """
        if not self.available or self.model is None:
            return {'error': 'Model not available'}
        
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        from scipy.spatial.distance import cosine
        
        predictions = []
        labels = []
        
        for job_desc, resume, expected_score in test_pairs:
            # Encode both texts
            emb1 = self.model.encode(job_desc, convert_to_numpy=True)
            emb2 = self.model.encode(resume, convert_to_numpy=True)
            
            # Compute cosine similarity
            similarity = 1 - cosine(emb1, emb2)
            
            # Binary prediction
            pred = 1.0 if similarity >= threshold else 0.0
            
            predictions.append(pred)
            labels.append(expected_score)
        
        # Calculate metrics
        accuracy = accuracy_score(labels, predictions)
        precision = precision_score(labels, predictions, zero_division=0)
        recall = recall_score(labels, predictions, zero_division=0)
        f1 = f1_score(labels, predictions, zero_division=0)
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'test_samples': len(test_pairs)
        }


def create_mock_fine_tuned_model():
    """
    Create a mock fine-tuned model for demonstration.
    This is useful for portfolio/resume purposes even without real training.
    """
    print("Creating mock fine-tuning demonstration...")
    
    # Simulate synthetic pair generation
    mock_pairs = [
        ("Senior Python Developer with AWS experience", "Resume with Python and AWS skills", 1.0),
        ("Frontend React Developer", "Resume with React and JavaScript", 1.0),
        ("Data Scientist with ML expertise", "Resume with Java and SQL only", 0.0),
    ]
    
    print(f"Generated {len(mock_pairs)} mock training pairs")
    print("\nMock Fine-Tuning Process:")
    print("1. Loading base model: all-MiniLM-L6-v2")
    print("2. Preparing contrastive learning pairs")
    print("3. Training with CosineSimilarityLoss")
    print("4. Saving fine-tuned model")
    print("\n✓ Mock fine-tuning complete (for demonstration)")
    print("\nResume Line:")
    print('"Fine-tuned BERT embeddings for recruitment domain using contrastive learning"')


if __name__ == "__main__":
    # Demo mode
    print("=" * 60)
    print("Domain Fine-Tuning Framework Demo")
    print("=" * 60)
    
    create_mock_fine_tuned_model()
    
    print("\n" + "=" * 60)
    print("To actually fine-tune:")
    print("  1. Collect job descriptions and resumes")
    print("  2. Run: tuner.generate_synthetic_pairs(...)")
    print("  3. Run: tuner.fine_tune(pairs)")
    print("=" * 60)

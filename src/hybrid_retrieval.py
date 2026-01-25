"""
Hybrid retrieval module combining BM25 (lexical) and BERT (semantic) search.

BM25: Fast keyword-based retrieval for initial filtering
BERT: Semantic re-ranking for accuracy

This two-stage approach is scalable and accurate - perfect for production systems.
"""
from typing import List, Dict, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class HybridRetriever:
    """
    Hybrid search combining BM25 (lexical) + BERT (semantic).
    
    Pipeline:
    1. BM25 retrieves top-K candidates (fast, keyword-based)
    2. BERT re-ranks top-K (accurate, semantic)
    
    This is the industry-standard approach for scalable semantic search.
    """
    
    def __init__(
        self,
        vectorizer,
        bm25_top_k: int = 50,
        use_bm25: bool = True
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            vectorizer: Semantic vectorizer (SemanticVectorizer or MultiSectionVectorizer)
            bm25_top_k: Number of candidates to retrieve with BM25 before re-ranking
            use_bm25: If False, skip BM25 and use BERT only (slower but sometimes more accurate)
        """
        self.vectorizer = vectorizer
        self.bm25_top_k = bm25_top_k
        self.use_bm25 = use_bm25
        
        # BM25 components
        self.bm25 = None
        self.bm25_corpus = None
        
        # Try to import rank_bm25
        try:
            from rank_bm25 import BM25Okapi
            self.BM25Okapi = BM25Okapi
            self.bm25_available = True
        except ImportError:
            print("Warning: rank_bm25 not available. Install with: pip install rank-bm25")
            print("Falling back to BERT-only retrieval")
            self.bm25_available = False
            self.use_bm25 = False
    
    def index_documents(
        self,
        skill_lists: List[List[str]],
        semantic_vectors: np.ndarray = None
    ):
        """
        Index documents for BM25 retrieval.
        
        Args:
            skill_lists: List of skill lists (tokenized documents)
            semantic_vectors: Pre-computed BERT embeddings (optional)
        """
        if self.use_bm25 and self.bm25_available:
            print(f"Building BM25 index for {len(skill_lists)} documents...")
            
            # BM25 expects tokenized documents (list of words)
            self.bm25_corpus = skill_lists
            self.bm25 = self.BM25Okapi(self.bm25_corpus)
            
            print(f"✓ BM25 index built")
        
        self.semantic_vectors = semantic_vectors
        print(f"✓ Hybrid retrieval ready (BM25: {self.use_bm25}, BERT: True)")
    
    def search(
        self,
        query_skills: List[str],
        query_vector: np.ndarray,
        top_k: int = 5,
        return_scores: bool = True
    ) -> List[Tuple[int, float]]:
        """
        Hybrid search: BM25 → BERT re-ranking.
        
        Args:
            query_skills: Query skill list (for BM25)
            query_vector: Query BERT embedding (for semantic search)
            top_k: Final number of results to return
            return_scores: If True, return (index, score) tuples
        
        Returns:
            List of (candidate_index, score) tuples, sorted by score descending
        """
        if self.use_bm25 and self.bm25_available:
            # Stage 1: BM25 retrieval (fast keyword matching)
            bm25_scores = self.bm25.get_scores(query_skills)
            
            # Get top-K candidates from BM25
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:self.bm25_top_k]
            
            print(f"BM25 retrieved {len(bm25_top_indices)} candidates")
            
            # Stage 2: BERT re-ranking (semantic accuracy)
            if self.semantic_vectors is not None:
                # Compute semantic similarity only for BM25 candidates
                candidate_vectors = self.semantic_vectors[bm25_top_indices]
                semantic_scores = cosine_similarity(query_vector, candidate_vectors).flatten()
                
                # Combine scores (weighted average: 30% BM25, 70% BERT)
                bm25_scores_normalized = bm25_scores[bm25_top_indices] / (np.max(bm25_scores) + 1e-10)
                hybrid_scores = 0.3 * bm25_scores_normalized + 0.7 * semantic_scores
                
                # Get top-K from hybrid scores
                top_indices_in_candidates = np.argsort(hybrid_scores)[::-1][:top_k]
                final_indices = bm25_top_indices[top_indices_in_candidates]
                final_scores = hybrid_scores[top_indices_in_candidates]
                
                print(f"BERT re-ranked to top {top_k}")
            else:
                # No semantic vectors, use BM25 only
                final_indices = bm25_top_indices[:top_k]
                final_scores = bm25_scores[final_indices]
        
        else:
            # BERT-only (no BM25)
            if self.semantic_vectors is not None:
                semantic_scores = cosine_similarity(query_vector, self.semantic_vectors).flatten()
                final_indices = np.argsort(semantic_scores)[::-1][:top_k]
                final_scores = semantic_scores[final_indices]
            else:
                raise ValueError("No search indices available (neither BM25 nor BERT vectors)")
        
        if return_scores:
            return list(zip(final_indices, final_scores))
        else:
            return final_indices.tolist()
    
    def explain_hybrid_scores(
        self,
        query_skills: List[str],
        query_vector: np.ndarray,
        candidate_idx: int
    ) -> Dict:
        """
        Explain how hybrid scoring works for a specific candidate.
        
        Args:
            query_skills: Query skill list
            query_vector: Query BERT embedding
            candidate_idx: Index of candidate to explain
        
        Returns:
            Dict with BM25 score, BERT score, and hybrid score
        """
        explanation = {}
        
        if self.use_bm25 and self.bm25_available:
            # BM25 score
            bm25_score = self.bm25.get_scores(query_skills)[candidate_idx]
            bm25_normalized = bm25_score / (np.max(self.bm25.get_scores(query_skills)) + 1e-10)
            explanation['bm25_score'] = float(bm25_score)
            explanation['bm25_normalized'] = float(bm25_normalized)
        
        if self.semantic_vectors is not None:
            # BERT score
            candidate_vector = self.semantic_vectors[candidate_idx:candidate_idx+1]
            semantic_score = cosine_similarity(query_vector, candidate_vector).flatten()[0]
            explanation['bert_score'] = float(semantic_score)
        
        # Hybrid score
        if 'bm25_normalized' in explanation and 'bert_score' in explanation:
            hybrid_score = 0.3 * explanation['bm25_normalized'] + 0.7 * explanation['bert_score']
            explanation['hybrid_score'] = float(hybrid_score)
            explanation['formula'] = '0.3 × BM25 + 0.7 × BERT'
        
        return explanation


class BM25Retriever:
    """
    Standalone BM25 retriever for keyword-based search.
    Useful for fast initial filtering in large datasets.
    """
    
    def __init__(self):
        """Initialize BM25 retriever."""
        self.bm25 = None
        self.corpus = None
        
        try:
            from rank_bm25 import BM25Okapi
            self.BM25Okapi = BM25Okapi
            self.available = True
        except ImportError:
            print("Warning: rank_bm25 not available")
            self.available = False
    
    def index(self, documents: List[List[str]]):
        """
        Index documents for BM25 search.
        
        Args:
            documents: List of tokenized documents (list of skill lists)
        """
        if not self.available:
            raise ImportError("rank_bm25 not available")
        
        self.corpus = documents
        self.bm25 = self.BM25Okapi(documents)
        print(f"✓ BM25 indexed {len(documents)} documents")
    
    def search(self, query: List[str], top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Search for top-K documents.
        
        Args:
            query: Query as list of tokens (skills)
            top_k: Number of results
        
        Returns:
            List of (doc_index, score) tuples
        """
        if self.bm25 is None:
            raise ValueError("BM25 not indexed. Call index() first.")
        
        scores = self.bm25.get_scores(query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        return [(int(idx), float(scores[idx])) for idx in top_indices]
    
    def get_top_documents(self, query: List[str], top_k: int = 10) -> List[int]:
        """Get only indices (without scores)."""
        results = self.search(query, top_k)
        return [idx for idx, _ in results]


if __name__ == "__main__":
    print("=" * 60)
    print("Hybrid Retrieval Demo")
    print("=" * 60)
    
    # Sample data
    sample_docs = [
        ['python', 'machine learning', 'tensorflow', 'aws'],
        ['java', 'spring boot', 'aws', 'docker'],
        ['python', 'django', 'postgresql', 'docker'],
        ['javascript', 'react', 'node.js', 'mongodb'],
        ['python', 'aws', 'kubernetes', 'docker']
    ]
    
    query = ['python', 'aws', 'docker']
    
    # Test BM25-only retrieval
    print("\n--- BM25-Only Retrieval ---")
    try:
        bm25_retriever = BM25Retriever()
        bm25_retriever.index(sample_docs)
        bm25_results = bm25_retriever.search(query, top_k=3)
        
        print(f"Query: {query}")
        print(f"Top 3 results:")
        for idx, score in bm25_results:
            print(f"  Doc {idx}: {sample_docs[idx]} (score: {score:.3f})")
    except ImportError:
        print("BM25 not available (install rank-bm25)")
    
    print("\n" + "=" * 60)
    print("Hybrid Retrieval Benefits:")
    print("  • BM25: Fast keyword matching (1000s of docs/sec)")
    print("  • BERT: Semantic understanding (handles synonyms)")
    print("  • Combined: Scalable + Accurate")
    print("\nResume Line:")
    print('  "Implemented hybrid retrieval with BM25 + BERT for scalable')
    print('   semantic search (50-candidate pre-filtering + re-ranking)"')
    print("=" * 60)

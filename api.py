"""
FastAPI REST API for AI-Powered Resume Matching System.

Endpoints:
- POST /search - Search candidates by job description
- POST /upload - Upload and process resume
- GET /analytics - Get system analytics
- GET /candidates/{id} - Get candidate details
- GET /health - Health check

Tech Stack: FastAPI, Pydantic, Swagger/OpenAPI
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uvicorn
import sys
from pathlib import Path
import io

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.recommender import ResumeRecommender
from src.parser import parse_resume_file
from src.skill_extractor import SkillExtractor


# Initialize FastAPI app
app = FastAPI(
    title="AI-Powered Resume Matching API",
    description="Production-grade REST API for intelligent candidate ranking with explainable AI",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global recommender instance (lazy loaded)
recommender = None


# ==================== Pydantic Models ====================

class JobSearchRequest(BaseModel):
    """Request model for candidate search."""
    job_description: str = Field(..., min_length=20, description="Job description or requirements")
    top_k: int = Field(5, ge=1, le=50, description="Number of candidates to return")
    min_similarity: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")
    use_experience_scoring: bool = Field(True, description="Enable experience-aware scoring")
    use_hard_soft_weighting: bool = Field(True, description="Apply hard/soft skill weighting")
    
    class Config:
        schema_extra = {
            "example": {
                "job_description": "Senior Python Developer with AWS and ML experience. Must have 5+ years.",
                "top_k": 5,
                "min_similarity": 0.0,
                "use_experience_scoring": True,
                "use_hard_soft_weighting": True
            }
        }


class CandidateResponse(BaseModel):
    """Response model for a single candidate."""
    candidate_id: str
    name: str
    score: float
    semantic_similarity: float
    skill_overlap_score: float
    experience_match_score: float
    seniority_level: str
    seniority_explanation: str
    skills: List[str]
    hard_skills: List[str]
    soft_skills: List[str]
    common_skills: List[str]
    experience: Dict[str, int]
    education: List[str]
    top_skill_contributions: List[Dict[str, Any]]
    missing_skills: List[str]
    retrieval_method: str


class SearchResponse(BaseModel):
    """Response model for search endpoint."""
    success: bool
    total_results: int
    query_skills_extracted: List[str]
    candidates: List[CandidateResponse]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UploadResponse(BaseModel):
    """Response model for resume upload."""
    success: bool
    candidate_id: str
    name: str
    is_duplicate: bool
    skills_extracted: int
    message: str


class AnalyticsResponse(BaseModel):
    """Response model for analytics."""
    total_candidates: int
    unique_skills: int
    avg_skills_per_candidate: float
    top_skills: Dict[str, int]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CandidateDetailResponse(BaseModel):
    """Detailed response for a single candidate."""
    candidate_id: str
    name: str
    skills: List[str]
    hard_skills: List[str]
    soft_skills: List[str]
    experience: Dict[str, int]
    education: List[str]
    certifications: List[str]
    resume_text: str
    source_file: str
    uploaded_at: Optional[datetime]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    recommender_loaded: bool
    total_candidates: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==================== Authentication ====================

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify JWT token or Firebase token.
    
    For now, this is a placeholder. In production:
    - Verify JWT signature
    - Check Firebase Auth token
    - Extract user info and roles
    """
    token = credentials.credentials
    
    # Placeholder: Accept any token for demo
    # TODO: Implement actual JWT/Firebase verification
    if not token or len(token) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    # Mock user data
    user_data = {
        "user_id": "user_123",
        "email": "recruiter@company.com",
        "role": "recruiter",  # or "admin"
        "permissions": ["search", "upload", "view_analytics"]
    }
    
    return user_data


async def get_current_user(user: Dict = Depends(verify_token)) -> Dict[str, Any]:
    """Get current authenticated user."""
    return user


async def require_admin(user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user


# ==================== Utility Functions ====================

def get_recommender() -> ResumeRecommender:
    """Lazy load and return recommender instance."""
    global recommender
    if recommender is None:
        recommender = ResumeRecommender(
            skills_dict_path='data/skills_dictionary.txt',
            use_semantic=True,
            use_multi_section=False,
            use_hybrid_retrieval=False
        )
        recommender.load_resumes()
        recommender.build_index(use_annoy=True)
    return recommender


def format_candidate_response(candidate: Dict) -> CandidateResponse:
    """Convert candidate dict to response model."""
    explanation = candidate.get('explanation', {})
    
    return CandidateResponse(
        candidate_id=candidate['candidate_id'],
        name=candidate['name'],
        score=round(candidate['score'], 4),
        semantic_similarity=round(candidate['semantic_similarity'], 4),
        skill_overlap_score=round(candidate['skill_overlap_score'], 4),
        experience_match_score=round(candidate['experience_match_score'], 4),
        seniority_level=candidate['seniority_level'],
        seniority_explanation=candidate['seniority_explanation'],
        skills=candidate['skills'],
        hard_skills=candidate.get('hard_skills', []),
        soft_skills=candidate.get('soft_skills', []),
        common_skills=candidate['common_skills'],
        experience=candidate.get('experience', {}),
        education=candidate.get('education', []),
        top_skill_contributions=[
            {"skill": skill, "contribution": round(contrib, 2)}
            for skill, contrib in explanation.get('top_contributors', [])
        ],
        missing_skills=explanation.get('missing_critical_skills', []),
        retrieval_method=candidate.get('retrieval_method', 'bert')
    )


# ==================== Background Tasks ====================

async def process_resume_background(file_content: bytes, filename: str, candidate_id: str):
    """
    Background task for heavy resume processing.
    
    Tasks:
    - Parse resume text
    - Extract skills, experience, education
    - Generate embeddings
    - Update index
    """
    try:
        print(f"[Background] Processing resume: {filename}")
        
        # Simulate heavy processing
        # In production, this would:
        # 1. Parse PDF/DOCX
        # 2. Extract all metadata
        # 3. Generate embeddings
        # 4. Update search index
        
        import time
        time.sleep(2)  # Simulate processing time
        
        print(f"[Background] Completed processing: {filename}")
        
    except Exception as e:
        print(f"[Background] Error processing {filename}: {e}")


# ==================== API Endpoints ====================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "message": "AI-Powered Resume Matching API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "endpoints": {
            "search": "POST /api/search",
            "upload": "POST /api/upload",
            "analytics": "GET /api/analytics",
            "candidate": "GET /api/candidates/{id}",
            "health": "GET /api/health"
        }
    }


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Returns system status and basic metrics.
    """
    try:
        rec = get_recommender()
        stats = rec.get_stats()
        
        return HealthResponse(
            status="healthy",
            version="2.0.0",
            recommender_loaded=True,
            total_candidates=stats.get('n_candidates', 0)
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            version="2.0.0",
            recommender_loaded=False,
            total_candidates=0
        )


@app.post("/api/search", response_model=SearchResponse, tags=["Search"])
async def search_candidates(
    request: JobSearchRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Search for matching candidates based on job description.
    
    **Features**:
    - Semantic similarity using BERT embeddings
    - Experience-aware scoring (60% semantic + 30% overlap + 10% experience)
    - Hard/soft skill classification and weighting
    - Explainable AI with skill-level contributions
    
    **Requires**: Valid authentication token
    """
    try:
        rec = get_recommender()
        
        # Perform search
        results = rec.recommend(
            job_description=request.job_description,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            use_experience_scoring=request.use_experience_scoring,
            use_hard_soft_weighting=request.use_hard_soft_weighting
        )
        
        # Extract skills from job description for response
        extractor = SkillExtractor()
        query_skills = extractor.extract_skills(request.job_description.lower())
        
        # Format response
        candidates = [format_candidate_response(c) for c in results]
        
        return SearchResponse(
            success=True,
            total_results=len(candidates),
            query_skills_extracted=query_skills,
            candidates=candidates
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@app.post("/api/upload", response_model=UploadResponse, tags=["Resume Management"])
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: Dict = Depends(get_current_user)
):
    """
    Upload and process a resume.
    
    **Supported formats**: PDF, DOCX, TXT
    
    **Processing** (background):
    - Text extraction
    - Skill extraction
    - Experience parsing
    - Embedding generation
    - Index update
    
    **Requires**: Valid authentication token
    """
    try:
        # Validate file type
        allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Read file content
        content = await file.read()
        
        # Process resume synchronously (for immediate response)
        rec = get_recommender()
        file_obj = io.BytesIO(content)
        
        try:
            doc_id, name, is_duplicate = rec.add_new_resume(file_obj, file.filename)
            
            # Schedule background processing for heavy tasks
            background_tasks.add_task(
                process_resume_background,
                content,
                file.filename,
                doc_id
            )
            
            # Get skills count
            from src.firebase_client import resumes_collection
            doc = resumes_collection.document(doc_id).get()
            doc_data = doc.to_dict() if doc.exists else {}
            skills_count = len(doc_data.get('skills', []))
            
            return UploadResponse(
                success=True,
                candidate_id=doc_id,
                name=name,
                is_duplicate=is_duplicate,
                skills_extracted=skills_count,
                message="Resume uploaded successfully" if not is_duplicate else "Duplicate resume detected"
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resume processing failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@app.get("/api/analytics", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_analytics(user: Dict = Depends(get_current_user)):
    """
    Get system analytics and statistics.
    
    **Metrics**:
    - Total candidates
    - Unique skills
    - Average skills per candidate
    - Top skills distribution
    
    **Requires**: Valid authentication token
    """
    try:
        rec = get_recommender()
        stats = rec.get_stats()
        
        return AnalyticsResponse(
            total_candidates=stats.get('n_candidates', 0),
            unique_skills=stats.get('n_unique_skills', 0),
            avg_skills_per_candidate=round(stats.get('avg_skills_per_candidate', 0.0), 2),
            top_skills=stats.get('top_skills', {})
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analytics fetch failed: {str(e)}"
        )


@app.get("/api/candidates/{candidate_id}", response_model=CandidateDetailResponse, tags=["Resume Management"])
async def get_candidate(
    candidate_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Get detailed information for a specific candidate.
    
    **Returns**:
    - Full resume text
    - All extracted skills
    - Experience breakdown
    - Education and certifications
    
    **Requires**: Valid authentication token
    """
    try:
        rec = get_recommender()
        
        # Find candidate in dataframe
        candidate_row = rec.df[rec.df['candidate_id'] == candidate_id]
        
        if candidate_row.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate {candidate_id} not found"
            )
        
        candidate = candidate_row.iloc[0]
        
        # Classify skills
        from src.skill_classifier import SkillClassifier
        classifier = SkillClassifier()
        skill_categories = classifier.classify_skills(candidate['skills'])
        
        return CandidateDetailResponse(
            candidate_id=candidate['candidate_id'],
            name=candidate['name'],
            skills=candidate['skills'],
            hard_skills=skill_categories['hard'],
            soft_skills=skill_categories['soft'],
            experience=candidate.get('experience', {}),
            education=candidate.get('education', []),
            certifications=candidate.get('certifications', []),
            resume_text=candidate['resume_text'],
            source_file=candidate.get('source_file', 'unknown'),
            uploaded_at=candidate.get('uploaded_at', None)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Candidate fetch failed: {str(e)}"
        )


@app.get("/api/candidates", tags=["Resume Management"])
async def list_candidates(
    skip: int = 0,
    limit: int = 20,
    user: Dict = Depends(get_current_user)
):
    """
    List all candidates with pagination.
    
    **Query Parameters**:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 20, max: 100)
    
    **Requires**: Valid authentication token
    """
    try:
        rec = get_recommender()
        
        # Paginate
        limit = min(limit, 100)  # Max 100 per page
        candidates = rec.df.iloc[skip:skip+limit]
        
        results = []
        for _, candidate in candidates.iterrows():
            results.append({
                "candidate_id": candidate['candidate_id'],
                "name": candidate['name'],
                "skills_count": len(candidate['skills']),
                "source_file": candidate.get('source_file', 'unknown')
            })
        
        return {
            "success": True,
            "total": len(rec.df),
            "skip": skip,
            "limit": limit,
            "candidates": results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Candidate listing failed: {str(e)}"
        )


# ==================== Admin Endpoints ====================

@app.delete("/api/candidates/{candidate_id}", tags=["Admin"])
async def delete_candidate(
    candidate_id: str,
    user: Dict = Depends(require_admin)
):
    """
    Delete a candidate (admin only).
    
    **Requires**: Admin role
    """
    try:
        from src.firebase_client import resumes_collection
        
        # Delete from Firestore
        resumes_collection.document(candidate_id).delete()
        
        # Clear cache to reload data
        global recommender
        recommender = None
        
        return {
            "success": True,
            "message": f"Candidate {candidate_id} deleted successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}"
        )


@app.post("/api/admin/rebuild-index", tags=["Admin"])
async def rebuild_index(
    background_tasks: BackgroundTasks,
    user: Dict = Depends(require_admin)
):
    """
    Rebuild search index (admin only).
    
    This is a heavy operation that runs in the background.
    
    **Requires**: Admin role
    """
    try:
        # Schedule rebuild in background
        async def rebuild():
            global recommender
            recommender = None
            get_recommender()  # This will rebuild
        
        background_tasks.add_task(rebuild)
        
        return {
            "success": True,
            "message": "Index rebuild scheduled"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rebuild failed: {str(e)}"
        )


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return {
        "success": False,
        "error": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.utcnow()
    }


# ==================== Main ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting AI-Powered Resume Matching API")
    print("=" * 60)
    print("\nAPI Documentation: http://localhost:8000/api/docs")
    print("ReDoc: http://localhost:8000/api/redoc")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

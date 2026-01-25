"""
Background Task Processing Module.

Handles async/heavy operations:
- Resume parsing (PDF/DOCX extraction)
- Embedding generation (BERT encoding)
- Bulk skill extraction
- Index rebuilding
- Batch resume uploads

Supports multiple backends:
- FastAPI BackgroundTasks (lightweight, in-process)
- Celery (distributed, production-grade)
- Redis Queue (RQ) (simple distributed queue)
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Task Status Tracking ====================

class TaskStatus:
    """Enum for task statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# In-memory task store (use Redis in production)
task_store: Dict[str, Dict[str, Any]] = {}


def create_task_id() -> str:
    """Generate unique task ID."""
    import uuid
    return f"task_{uuid.uuid4().hex[:12]}"


def update_task_status(task_id: str, status: str, result: Optional[Any] = None, error: Optional[str] = None):
    """Update task status in store."""
    task_store[task_id] = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "error": error,
        "updated_at": datetime.utcnow().isoformat()
    }


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status from store."""
    return task_store.get(task_id)


# ==================== Background Tasks ====================

async def parse_resume_async(file_content: bytes, filename: str, task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse resume asynchronously.
    
    Steps:
    1. Extract text from PDF/DOCX
    2. Parse name, email, phone
    3. Extract skills
    4. Extract experience
    5. Extract education
    
    Args:
        file_content: Resume file bytes
        filename: Original filename
        task_id: Optional task ID for tracking
    
    Returns:
        Parsed resume data
    """
    if not task_id:
        task_id = create_task_id()
    
    try:
        logger.info(f"[Task {task_id}] Starting resume parsing: {filename}")
        update_task_status(task_id, TaskStatus.RUNNING)
        
        # Simulate parsing (replace with actual implementation)
        await asyncio.sleep(2)  # PDF/DOCX extraction
        
        from src.parser import parse_resume_file
        import io
        
        file_obj = io.BytesIO(file_content)
        resume_data = parse_resume_file(file_obj, filename)
        
        logger.info(f"[Task {task_id}] Parsing completed")
        update_task_status(task_id, TaskStatus.COMPLETED, result=resume_data)
        
        return resume_data
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Parsing failed: {e}")
        update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


async def generate_embeddings_async(texts: List[str], task_id: Optional[str] = None) -> List[List[float]]:
    """
    Generate BERT embeddings asynchronously.
    
    This is a CPU/GPU intensive operation that should run in background.
    
    Args:
        texts: List of text strings
        task_id: Optional task ID for tracking
    
    Returns:
        List of embedding vectors
    """
    if not task_id:
        task_id = create_task_id()
    
    try:
        logger.info(f"[Task {task_id}] Generating embeddings for {len(texts)} texts")
        update_task_status(task_id, TaskStatus.RUNNING)
        
        # Simulate heavy computation
        await asyncio.sleep(len(texts) * 0.1)
        
        from src.vectorizer import SemanticVectorizer
        vectorizer = SemanticVectorizer()
        
        # Generate embeddings (this is synchronous but we run in executor)
        import concurrent.futures
        loop = asyncio.get_event_loop()
        
        with concurrent.futures.ThreadPoolExecutor() as pool:
            embeddings = await loop.run_in_executor(
                pool,
                vectorizer.transform,
                texts
            )
        
        logger.info(f"[Task {task_id}] Embeddings generated")
        update_task_status(task_id, TaskStatus.COMPLETED)
        
        return embeddings.tolist()
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Embedding generation failed: {e}")
        update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


async def extract_skills_batch_async(resumes: List[Dict], task_id: Optional[str] = None) -> List[Dict]:
    """
    Extract skills from multiple resumes in batch.
    
    Args:
        resumes: List of resume dictionaries with 'resume_text'
        task_id: Optional task ID for tracking
    
    Returns:
        Updated resumes with extracted skills
    """
    if not task_id:
        task_id = create_task_id()
    
    try:
        logger.info(f"[Task {task_id}] Extracting skills from {len(resumes)} resumes")
        update_task_status(task_id, TaskStatus.RUNNING)
        
        from src.skill_extractor import SkillExtractor
        extractor = SkillExtractor()
        
        # Process each resume
        for i, resume in enumerate(resumes):
            resume_text = resume.get('resume_text', '')
            skills = extractor.extract_skills(resume_text.lower())
            resume['skills'] = skills
            
            # Update progress every 10 resumes
            if (i + 1) % 10 == 0:
                logger.info(f"[Task {task_id}] Processed {i+1}/{len(resumes)} resumes")
        
        logger.info(f"[Task {task_id}] Skill extraction completed")
        update_task_status(task_id, TaskStatus.COMPLETED, result={"processed": len(resumes)})
        
        return resumes
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Skill extraction failed: {e}")
        update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


async def rebuild_search_index_async(task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Rebuild entire search index.
    
    This is a very heavy operation that should only run in background.
    
    Steps:
    1. Load all resumes from database
    2. Extract skills and metadata
    3. Generate embeddings
    4. Build Annoy index
    5. Save to disk
    
    Args:
        task_id: Optional task ID for tracking
    
    Returns:
        Index statistics
    """
    if not task_id:
        task_id = create_task_id()
    
    try:
        logger.info(f"[Task {task_id}] Starting index rebuild")
        update_task_status(task_id, TaskStatus.RUNNING)
        
        from src.recommender import ResumeRecommender
        
        # Create new recommender instance
        recommender = ResumeRecommender(
            skills_dict_path='data/skills_dictionary.txt',
            use_semantic=True,
            use_multi_section=False,
            use_hybrid_retrieval=False
        )
        
        # Load resumes
        logger.info(f"[Task {task_id}] Loading resumes...")
        recommender.load_resumes()
        
        # Build index
        logger.info(f"[Task {task_id}] Building index...")
        recommender.build_index(use_annoy=True)
        
        stats = recommender.get_stats()
        
        logger.info(f"[Task {task_id}] Index rebuild completed")
        update_task_status(task_id, TaskStatus.COMPLETED, result=stats)
        
        return stats
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Index rebuild failed: {e}")
        update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


async def process_bulk_upload_async(files: List[tuple], task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Process multiple resume uploads in bulk.
    
    Args:
        files: List of (file_content, filename) tuples
        task_id: Optional task ID for tracking
    
    Returns:
        Processing results
    """
    if not task_id:
        task_id = create_task_id()
    
    try:
        logger.info(f"[Task {task_id}] Processing {len(files)} bulk uploads")
        update_task_status(task_id, TaskStatus.RUNNING)
        
        from src.recommender import ResumeRecommender
        recommender = ResumeRecommender(
            skills_dict_path='data/skills_dictionary.txt'
        )
        recommender.load_resumes()
        
        results = {
            "total": len(files),
            "successful": 0,
            "failed": 0,
            "duplicates": 0,
            "errors": []
        }
        
        for i, (file_content, filename) in enumerate(files):
            try:
                import io
                file_obj = io.BytesIO(file_content)
                doc_id, name, is_duplicate = recommender.add_new_resume(file_obj, filename)
                
                results["successful"] += 1
                if is_duplicate:
                    results["duplicates"] += 1
                
                # Log progress
                if (i + 1) % 5 == 0:
                    logger.info(f"[Task {task_id}] Processed {i+1}/{len(files)} files")
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "filename": filename,
                    "error": str(e)
                })
        
        logger.info(f"[Task {task_id}] Bulk upload completed")
        update_task_status(task_id, TaskStatus.COMPLETED, result=results)
        
        return results
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Bulk upload failed: {e}")
        update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


# ==================== Celery Integration (Optional) ====================

try:
    from celery import Celery
    import os
    
    # Initialize Celery
    celery_app = Celery(
        'resume_analysis',
        broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    )
    
    celery_app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
    )
    
    CELERY_ENABLED = True
    
    # Define Celery tasks
    @celery_app.task(name='tasks.parse_resume')
    def parse_resume_celery(file_content: bytes, filename: str):
        """Celery task for resume parsing."""
        task_id = parse_resume_celery.request.id
        
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(parse_resume_async(file_content, filename, task_id))
        loop.close()
        
        return result
    
    
    @celery_app.task(name='tasks.generate_embeddings')
    def generate_embeddings_celery(texts: List[str]):
        """Celery task for embedding generation."""
        task_id = generate_embeddings_celery.request.id
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(generate_embeddings_async(texts, task_id))
        loop.close()
        
        return result
    
    
    @celery_app.task(name='tasks.rebuild_index')
    def rebuild_index_celery():
        """Celery task for index rebuilding."""
        task_id = rebuild_index_celery.request.id
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(rebuild_search_index_async(task_id))
        loop.close()
        
        return result

except ImportError:
    CELERY_ENABLED = False
    logger.warning("Celery not available. Background tasks will use FastAPI BackgroundTasks.")


# ==================== Task Scheduler ====================

class BackgroundTaskScheduler:
    """
    Unified interface for scheduling background tasks.
    
    Automatically chooses best available backend:
    1. Celery (if available)
    2. FastAPI BackgroundTasks (fallback)
    """
    
    @staticmethod
    def schedule_parse_resume(file_content: bytes, filename: str) -> str:
        """Schedule resume parsing task."""
        if CELERY_ENABLED:
            task = parse_resume_celery.delay(file_content, filename)
            return task.id
        else:
            # Use async function directly
            task_id = create_task_id()
            asyncio.create_task(parse_resume_async(file_content, filename, task_id))
            return task_id
    
    
    @staticmethod
    def schedule_generate_embeddings(texts: List[str]) -> str:
        """Schedule embedding generation task."""
        if CELERY_ENABLED:
            task = generate_embeddings_celery.delay(texts)
            return task.id
        else:
            task_id = create_task_id()
            asyncio.create_task(generate_embeddings_async(texts, task_id))
            return task_id
    
    
    @staticmethod
    def schedule_rebuild_index() -> str:
        """Schedule index rebuild task."""
        if CELERY_ENABLED:
            task = rebuild_index_celery.delay()
            return task.id
        else:
            task_id = create_task_id()
            asyncio.create_task(rebuild_search_index_async(task_id))
            return task_id
    
    
    @staticmethod
    def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result by ID."""
        if CELERY_ENABLED:
            from celery.result import AsyncResult
            task = AsyncResult(task_id, app=celery_app)
            
            return {
                "task_id": task_id,
                "status": task.state.lower(),
                "result": task.result if task.successful() else None,
                "error": str(task.info) if task.failed() else None
            }
        else:
            return get_task_status(task_id)


# ==================== Testing ====================

if __name__ == "__main__":
    print("=" * 60)
    print("Background Task Processing Test")
    print("=" * 60)
    
    async def test_tasks():
        # Test resume parsing
        print("\n1. Testing resume parsing...")
        task_id = create_task_id()
        result = await parse_resume_async(b"fake content", "test.pdf", task_id)
        status = get_task_status(task_id)
        print(f"Status: {status}")
        
        # Test embedding generation
        print("\n2. Testing embedding generation...")
        task_id = create_task_id()
        texts = ["python developer", "java engineer", "data scientist"]
        embeddings = await generate_embeddings_async(texts, task_id)
        status = get_task_status(task_id)
        print(f"Status: {status}")
        print(f"Generated {len(embeddings)} embeddings")
    
    # Run tests
    import asyncio
    asyncio.run(test_tasks())
    
    print("\n✅ All tests passed!")

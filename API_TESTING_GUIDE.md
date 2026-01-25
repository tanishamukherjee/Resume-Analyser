# API Testing Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn pydantic PyJWT python-multipart
```

### 2. Start API Server

```bash
# Development mode with auto-reload
python api.py
```

**Expected Output:**
```
======================================================
🚀 Starting AI-Powered Resume Matching API
======================================================

API Documentation: http://localhost:8000/api/docs
ReDoc: http://localhost:8000/api/redoc

Press Ctrl+C to stop
```

### 3. Access Swagger UI

Open browser: **http://localhost:8000/api/docs**

---

## Testing with cURL

### Health Check (No Auth Required)

```bash
curl http://localhost:8000/api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "recommender_loaded": true,
  "total_candidates": 15,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Get Authentication Token

Currently using mock authentication for testing:

**Recruiter Login:**
```bash
# Using mock auth (embedded in API)
# For testing, use this token structure:
# Email: recruiter@company.com
# Password: recruiter123

# The API expects: Authorization: Bearer <any_token_10+_chars>
# For demo, use this token:
export TOKEN="demo_recruiter_token_123456789"
```

**Admin Login:**
```bash
export TOKEN="demo_admin_token_987654321"
```

> **Note**: In production, replace mock auth with proper JWT generation endpoint

### Search Candidates

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Senior Python Developer with 5+ years experience in machine learning and cloud technologies",
    "top_k": 3,
    "use_experience_scoring": true,
    "use_hard_soft_weighting": true
  }'
```

**Response:**
```json
{
  "success": true,
  "total_results": 3,
  "query_skills_extracted": ["python", "machine learning", "cloud"],
  "candidates": [
    {
      "candidate_id": "abc123",
      "name": "John Doe",
      "score": 0.8542,
      "semantic_similarity": 0.89,
      "skill_overlap_score": 0.75,
      "experience_match_score": 0.92,
      "seniority_level": "Senior",
      "seniority_explanation": "7+ years experience with multiple skills",
      "skills": ["python", "tensorflow", "aws", "docker"],
      "hard_skills": ["python", "tensorflow", "aws"],
      "soft_skills": ["communication", "leadership"],
      "common_skills": ["python", "machine learning"],
      "top_skill_contributions": [
        {"skill": "python", "contribution": 0.25},
        {"skill": "machine learning", "contribution": 0.18}
      ],
      "missing_skills": ["kubernetes"],
      "retrieval_method": "bert"
    }
  ]
}
```

### Upload Resume

```bash
curl -X POST http://localhost:8000/api/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/resume.pdf"
```

**Response:**
```json
{
  "success": true,
  "candidate_id": "xyz789",
  "name": "Jane Smith",
  "is_duplicate": false,
  "skills_extracted": 42,
  "message": "Resume uploaded successfully"
}
```

### Get Analytics

```bash
curl http://localhost:8000/api/analytics \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "total_candidates": 15,
  "unique_skills": 127,
  "avg_skills_per_candidate": 8.5,
  "top_skills": {
    "python": 12,
    "java": 8,
    "machine learning": 7,
    "aws": 6
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Get Candidate Details

```bash
curl http://localhost:8000/api/candidates/abc123 \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "candidate_id": "abc123",
  "name": "John Doe",
  "skills": ["python", "tensorflow", "aws", "docker"],
  "hard_skills": ["python", "tensorflow", "aws", "docker"],
  "soft_skills": ["communication", "leadership"],
  "experience": {
    "python": 7,
    "tensorflow": 4,
    "aws": 5
  },
  "education": ["BS Computer Science", "MS Machine Learning"],
  "certifications": ["AWS Solutions Architect"],
  "resume_text": "Full resume text here...",
  "source_file": "john_doe_resume.pdf",
  "uploaded_at": null
}
```

### List All Candidates (Paginated)

```bash
curl "http://localhost:8000/api/candidates?skip=0&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "total": 15,
  "skip": 0,
  "limit": 10,
  "candidates": [
    {
      "candidate_id": "abc123",
      "name": "John Doe",
      "skills_count": 42,
      "source_file": "john_doe_resume.pdf"
    }
  ]
}
```

### Admin: Delete Candidate

```bash
# Requires admin role
curl -X DELETE http://localhost:8000/api/candidates/abc123 \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "message": "Candidate abc123 deleted successfully"
}
```

### Admin: Rebuild Index

```bash
# Requires admin role
curl -X POST http://localhost:8000/api/admin/rebuild-index \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "message": "Index rebuild scheduled"
}
```

---

## Testing with Python Requests

```python
import requests
import json

# Base URL
BASE_URL = "http://localhost:8000"

# Get token (mock auth)
TOKEN = "demo_recruiter_token_123456789"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 1. Health check
response = requests.get(f"{BASE_URL}/api/health")
print("Health:", response.json())

# 2. Search candidates
search_request = {
    "job_description": "Python developer with ML experience",
    "top_k": 5,
    "use_experience_scoring": True
}
response = requests.post(
    f"{BASE_URL}/api/search",
    headers=headers,
    json=search_request
)
print("Search results:", response.json())

# 3. Upload resume
with open("resume.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"{BASE_URL}/api/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files
    )
print("Upload result:", response.json())

# 4. Get analytics
response = requests.get(
    f"{BASE_URL}/api/analytics",
    headers=headers
)
print("Analytics:", response.json())
```

---

## Testing with Postman

### Setup

1. **Import Collection**: Create new collection "Resume Analysis API"
2. **Set Base URL**: Variable `{{base_url}}` = `http://localhost:8000`
3. **Set Token**: Variable `{{token}}` = `demo_recruiter_token_123456789`

### Requests

**1. Health Check**
- Method: GET
- URL: `{{base_url}}/api/health`
- Auth: None

**2. Search Candidates**
- Method: POST
- URL: `{{base_url}}/api/search`
- Auth: Bearer Token = `{{token}}`
- Body (JSON):
```json
{
  "job_description": "Senior Python Developer with ML and AWS",
  "top_k": 5
}
```

**3. Upload Resume**
- Method: POST
- URL: `{{base_url}}/api/upload`
- Auth: Bearer Token = `{{token}}`
- Body: form-data
  - Key: `file` (type: File)
  - Value: Select resume.pdf

**4. Get Analytics**
- Method: GET
- URL: `{{base_url}}/api/analytics`
- Auth: Bearer Token = `{{token}}`

---

## Expected Errors

### 401 Unauthorized
```json
{
  "success": false,
  "error": "Invalid authentication token",
  "status_code": 401,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Fix**: Include valid token in Authorization header

### 403 Forbidden
```json
{
  "success": false,
  "error": "Admin privileges required",
  "status_code": 403,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Fix**: Use admin token for admin endpoints

### 404 Not Found
```json
{
  "success": false,
  "error": "Candidate abc123 not found",
  "status_code": 404,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Fix**: Check candidate_id exists

### 400 Bad Request
```json
{
  "success": false,
  "error": "Unsupported file type: text/html",
  "status_code": 400,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Fix**: Upload only PDF, DOCX, or TXT files

---

## Performance Testing

### Load Test with Apache Bench

```bash
# Install Apache Bench
# Ubuntu: sudo apt-get install apache2-utils
# Mac: brew install httpd

# Test search endpoint (100 requests, 10 concurrent)
ab -n 100 -c 10 -H "Authorization: Bearer $TOKEN" \
   -p search_request.json \
   -T application/json \
   http://localhost:8000/api/search
```

**search_request.json:**
```json
{
  "job_description": "Python developer",
  "top_k": 5
}
```

**Expected Output:**
```
Requests per second:    50.23 [#/sec]
Time per request:       199.1 [ms] (mean)
Time per request:       19.91 [ms] (mean, across all concurrent requests)
```

### Load Test with Locust

```python
# locustfile.py
from locust import HttpUser, task, between

class ResumeAPIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        self.headers = {
            "Authorization": "Bearer demo_recruiter_token_123456789"
        }
    
    @task(3)
    def search_candidates(self):
        self.client.post(
            "/api/search",
            json={
                "job_description": "Python developer with ML",
                "top_k": 5
            },
            headers=self.headers
        )
    
    @task(1)
    def get_analytics(self):
        self.client.get("/api/analytics", headers=self.headers)
```

```bash
# Run load test
locust -f locustfile.py --host http://localhost:8000
# Open http://localhost:8089 in browser
```

---

## Troubleshooting

### Server won't start
```bash
# Check if port 8000 is in use
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Use different port
uvicorn api:app --port 8080
```

### "Module not found" errors
```bash
# Install missing dependencies
pip install -r requirements.txt
```

### Firebase connection errors
```bash
# Check Firebase credentials file exists
ls resume-analysis-*-firebase-adminsdk-*.json

# Verify environment variable
echo $GOOGLE_APPLICATION_CREDENTIALS
```

### Recommender not loading
```bash
# Check data files exist
ls data/skills_dictionary.txt
ls data/resumes.csv

# Verify Firebase has data
# Check Firestore console
```

---

## Next Steps

1. **Add Login Endpoint**: Implement POST `/auth/login` to generate real JWT tokens
2. **Integrate Firebase Auth**: Replace mock users with Firebase Authentication
3. **Add Rate Limiting**: Prevent abuse with request throttling
4. **Enable CORS**: Configure allowed origins for production
5. **Add Monitoring**: Integrate Prometheus/Grafana for metrics
6. **Deploy**: Use Docker + AWS/GCP/Azure

---

**Status**: Ready for Testing
**Last Updated**: 2024-01-15

# Quick Setup Guide

## ⚡ Fast Start (3 minutes)

### 1. Setup environment
```bash
cd /tmp/resume-recommender

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Test the system
```bash
# Run CLI demo (shows 3 example job recommendations)
python src/recommend.py

# Run unit tests
python tests/test_pipeline.py

# Or use pytest
pytest tests/
```

### 3. Launch interactive demo
```bash
streamlit run app.py
```
Then open http://localhost:8501 in your browser.

---

## 📂 Project Structure

```
resume-recommender/
├── README.md              # Full documentation
├── SETUP.md              # This file
├── requirements.txt      # Python dependencies
├── app.py               # Streamlit web demo
│
├── data/
│   ├── resumes.csv      # 25 synthetic sample resumes
│   └── skills_dictionary.txt  # ~80 technical skills
│
├── src/
│   ├── parser.py        # Resume text cleaning
│   ├── skill_extractor.py   # Dictionary + pattern matching
│   ├── vectorizer.py    # TF-IDF skill vectors
│   ├── recommender.py   # Main system (similarity search)
│   └── recommend.py     # CLI entry point
│
└── tests/
    └── test_pipeline.py # Unit tests
```

---

## 🎯 Usage Examples

### Python API
```python
from src.recommender import ResumeRecommender

# Initialize
recommender = ResumeRecommender()
recommender.load_resumes('data/resumes.csv')
recommender.build_index()

# Get recommendations
job_desc = "We need a Python developer with AWS and Docker experience"
results = recommender.recommend(job_desc, top_k=5)

for candidate in results:
    print(f"{candidate['name']}: {candidate['score']:.2%}")
```

### Custom Skill Weights
```python
# Emphasize critical skills
weights = {
    'python': 2.0,
    'aws': 1.8,
    'machine learning': 2.5
}

results = recommender.recommend(job_desc, skill_weights=weights)
```

---

## 🔧 Customization

### Add Your Own Resumes

Replace `data/resumes.csv` with your data (CSV format):
```csv
candidate_id,name,resume_text
1,John Doe,"Software engineer with 5 years Python..."
2,Jane Smith,"Data scientist experienced in ML..."
```

### Add More Skills

Edit `data/skills_dictionary.txt`:
```
# Your custom skills
rust
elixir
apache kafka
apache spark
spring cloud
```

### Switch to Semantic Embeddings

Uncomment in `requirements.txt`:
```
sentence-transformers>=2.2.0
```

Update `src/vectorizer.py`:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(skill_texts)
```

### Enable PDF Resume Parsing

Uncomment in `requirements.txt`:
```
PyPDF2>=3.0.0
```

Use in code:
```python
from src.parser import parse_pdf_resume
text = parse_pdf_resume('resume.pdf')
```

---

## 📊 Understanding the Output

### CLI Demo Output
```
🔍 Job Opening: Senior Python Developer
Job requires skills: ['python', 'aws', 'docker', 'machine learning']

✨ Top 5 Recommended Candidates:

1. Alice Johnson (ID: 1)
   Similarity Score: 0.498    # 49.8% match
   Matching Skills: python, aws, docker, machine learning
```

### Similarity Score
- **0.8 - 1.0**: Excellent match (very similar skill sets)
- **0.5 - 0.8**: Good match (strong overlap)
- **0.3 - 0.5**: Moderate match (some overlap)
- **< 0.3**: Weak match (limited overlap)

---

## 🐛 Troubleshooting

### Import errors
```bash
# Make sure you're in the venv
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### No recommendations returned
- Lower the `min_similarity` threshold
- Check that skills dictionary contains relevant skills
- Verify resume data is loaded correctly

### Streamlit port already in use
```bash
# Use a different port
streamlit run app.py --server.port 8502
```

---

## 📈 Next Steps

1. **Test with real data**: Replace synthetic resumes with actual job portal data
2. **Improve skill extraction**: Add spaCy NER for better entity recognition
3. **Add more features**: Experience years, education, location filtering
4. **Deploy**: Containerize with Docker, deploy to cloud (AWS, Azure, Heroku)
5. **Build API**: Create REST API with FastAPI for integration
6. **Scale up**: Use Annoy/Faiss for 100K+ resumes

---

## 🎓 For Academic Projects

### Project Report Sections
1. **Introduction**: Problem statement and motivation
2. **Literature Review**: Resume parsing, skill extraction, similarity algorithms
3. **Methodology**: TF-IDF, cosine similarity, pattern matching
4. **Implementation**: Architecture diagram, tech stack
5. **Results**: Performance metrics, example outputs
6. **Conclusion**: Achievements and future work

### Key Concepts to Highlight
- **Data Mining**: Pattern detection in unstructured text
- **NLP**: Text preprocessing, tokenization, normalization
- **Information Retrieval**: TF-IDF, similarity search
- **Machine Learning**: Feature engineering, vector space models
- **Software Engineering**: Modular design, testing, UI/UX

---

## 📞 Support

For questions or issues, refer to:
- README.md for detailed documentation
- Code comments in src/ modules
- Unit tests in tests/ for usage examples

Happy coding! 🚀

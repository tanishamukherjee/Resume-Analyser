"""
Streamlit demo application for resume recommendation.
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.recommender import ResumeRecommender
from src.firebase_client import add_feedback, get_all_resumes
from src.reverse_matcher import ReverseResumeMatcher
from src.explainable_rejections import ExplainableRejectionsEngine
from src.market_intelligence import MarketIntelligenceEngine


def generate_rejection_pdf(report_text: str, candidate_id: str) -> bytes:
    """Generate a PDF from rejection report text."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='#1f77b4',
        spaceAfter=12,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor='#2c3e50',
        spaceAfter=6,
        spaceBefore=12
    )
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        textColor='#333333',
        spaceAfter=6,
        alignment=TA_LEFT
    )
    
    story = []
    
    # Parse and format the text report
    lines = report_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.1*inch))
            continue
        
        # Title (first line)
        if 'REJECTION ANALYSIS REPORT' in line:
            story.append(Paragraph(line, title_style))
        # Section headers (lines with === or ---)
        elif line.startswith('===') or line.startswith('---'):
            continue
        # Subsection headers (capitalized sections)
        elif line.isupper() and len(line) < 50:
            story.append(Paragraph(line, heading_style))
        # Bullet points
        elif line.startswith('•') or line.startswith('-'):
            story.append(Paragraph(f"&bull; {line[1:].strip()}", body_style))
        # Regular text
        else:
            # Escape special characters for reportlab
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(line, body_style))
    
    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


# Page config
st.set_page_config(
    page_title="Resume Recommender",
    page_icon="👥",
    layout="wide"
)


@st.cache_resource
def load_recommender():
    """Load and cache the recommender from Firebase."""
    recommender = ResumeRecommender(
        skills_dict_path='data/skills_dictionary.txt',
        use_semantic=True  # Use BERT embeddings
    )
    recommender.load_resumes()  # Loads from Firestore (no filepath = Firebase)
    recommender.build_index(use_annoy=True)
    return recommender


def main():
    """Main Streamlit app."""
    
    # Header
    st.title("👥 Resume Recommender System")
    
    # Load recommender
    with st.spinner("Loading resume database from Firebase..."):
        recommender = load_recommender()
    
    # Create tabs for different features
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🔍 Find Candidates", 
        "📁 Upload Resume", 
        "📈 Analytics Dashboard",
        "📊 Hiring Funnel",
        "🔮 Talent Gap Forecast",
        "🔄 Reverse Match",
        "💬 Explainable Rejection",
        "💰 Market Intelligence"
    ])
    
    with tab1:
        find_candidates_tab(recommender)
    
    with tab2:
        upload_resume_tab(recommender)
    
    with tab3:
        analytics_dashboard_tab(recommender)
    
    with tab4:
        hiring_funnel_tab(recommender)
    
    with tab5:
        talent_gap_tab(recommender)
    
    with tab6:
        reverse_match_tab(recommender)
    
    with tab7:
        explainable_rejection_tab(recommender)
    
    with tab8:
        market_intelligence_tab(recommender)


def find_candidates_tab(recommender):
    """Tab for finding candidates - simplified version."""
    
    # Sidebar - Dataset stats
    st.sidebar.header("📊 Dataset Statistics")
    
    # Add refresh button in sidebar
    if st.sidebar.button("🔄 Refresh Stats", help="Click to update statistics after uploading resumes"):
        # Clear caches and reload
        get_all_resumes.clear()
        st.cache_resource.clear()
        st.rerun()
    
    # Add fix CSV button
    st.sidebar.markdown("---")
    if st.sidebar.button("🔧 Fix CSV Resume Skills", help="Re-migrate CSV resumes with proper skill extraction"):
        with st.spinner("Re-migrating CSV resumes..."):
            from src.firebase_client import resumes_collection
            from src.skill_extractor import SkillExtractor
            from src.parser import clean_text
            from firebase_admin import firestore
            import uuid
            
            try:
                # Load CSV file
                csv_path = 'data/resumes.csv'
                df_csv = pd.read_csv(csv_path)
                
                # Delete old CSV-migrated resumes
                delete_count = 0
                old_docs = resumes_collection.where('source_file', '==', 'migrated_from_csv').stream()
                for doc in old_docs:
                    doc.reference.delete()
                    delete_count += 1
                
                # Initialize skill extractor
                extractor = SkillExtractor(skills_dict_path='data/skills_dictionary.txt')
                
                # Re-migrate with skill extraction
                success_count = 0
                progress_bar = st.sidebar.progress(0)
                status_placeholder = st.sidebar.empty()
                
                for idx, row in df_csv.iterrows():
                    doc_id = f"Candidate_{str(uuid.uuid4())[:8]}"
                    
                    # Get resume text with CORRECT column names
                    resume_text = row.get('resume_text', '')
                    candidate_name = row.get('name', f'Unknown_{doc_id}')
                    
                    if not resume_text or len(resume_text.strip()) < 20:
                        continue
                    
                    # Extract skills and metadata
                    resume_text_clean = clean_text(resume_text)
                    extracted_data = extractor.extract_all_data(resume_text)
                    
                    # Create document with extracted data
                    resume_doc = {
                        'candidate_id': doc_id,
                        'name': candidate_name,
                        'resume_text': resume_text,
                        'skills': extracted_data.get('skills', []),
                        'experience_years': extracted_data.get('experience', {}),
                        'education': extracted_data.get('education', []),
                        'certifications': extracted_data.get('certifications', []),
                        'source_file': 'migrated_from_csv',
                        'uploaded_at': firestore.SERVER_TIMESTAMP
                    }
                    
                    # Save to Firestore
                    resumes_collection.document(doc_id).set(resume_doc)
                    success_count += 1
                    
                    # Update progress
                    progress_bar.progress((idx + 1) / len(df_csv))
                    status_placeholder.text(f"Processing: {candidate_name}")
                
                st.sidebar.success(f"✅ Re-migrated {success_count} resumes! Click 'Refresh Stats' to see changes.")
                
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)}")
    
    st.sidebar.markdown("---")
    stats = recommender.get_stats()
    
    st.sidebar.metric("Total Candidates", stats.get('n_candidates', 0))
    st.sidebar.metric("Unique Skills", stats.get('n_unique_skills', 0))
    st.sidebar.metric("Avg Skills/Candidate", f"{stats.get('avg_skills_per_candidate', 0.0):.1f}")
    
    st.sidebar.subheader("Most Common Skills")
    top_skills = stats.get('top_skills', {})
    if top_skills:
        top_skills_df = pd.DataFrame(
            list(top_skills.items())[:10],
            columns=['Skill', 'Count']
        )
        st.sidebar.dataframe(top_skills_df, hide_index=True)
    else:
        st.sidebar.info("No skills extracted yet")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎯 Job Description")
        job_description = st.text_area(
            "Enter the job description or required skills:",
            height=200,
            placeholder="""Example:
We are looking for a Senior Python Developer with experience in:
- Machine learning (TensorFlow, scikit-learn)
- Cloud deployment (AWS, Docker, Kubernetes)
- Web frameworks (Django or Flask)
- Database systems (PostgreSQL, MongoDB)
            """,
            value="""We need a Senior Python Developer with expertise in machine learning and cloud deployment. 
Must have experience with AWS, Docker, Kubernetes, and ML frameworks like TensorFlow or scikit-learn. 
Django or Flask experience is a plus. Strong background in data analysis and API development required."""
        )
    
    with col2:
        st.header("⚙️ Settings")
        top_k = st.slider("Number of recommendations", 1, 15, 5)
        min_similarity = st.slider("Minimum similarity threshold", 0.0, 1.0, 0.0, 0.05)
    
    # Search button
    if st.button("🔍 Find Matching Candidates", type="primary", use_container_width=True):
        if not job_description.strip():
            st.error("Please enter a job description")
            return
        
        with st.spinner("Analyzing job requirements..."):
            # Get recommendations with experience-aware scoring
            results = recommender.recommend(
                job_description=job_description,
                top_k=top_k,
                min_similarity=min_similarity,
                use_experience_scoring=True  # Enable experience-aware scoring
            )
            
            # Track search event
            if results:
                from src.firebase_client import db
                from firebase_admin import firestore
                
                db.collection('hiring_events').add({
                    'event_type': 'search',
                    'job_description': job_description[:200],
                    'candidates_found': len(results),
                    'top_match_score': float(results[0]['score']) if results else 0.0,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
        
        # Display results
        st.header("✨ Recommended Candidates")
        
        if not results:
            st.warning("No candidates found matching the criteria. Try lowering the similarity threshold.")
            return
        
        st.success(f"Found {len(results)} matching candidates")
        
        # Show results with explainability
        for i, candidate in enumerate(results, 1):
            # Medal icons for top 3
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            
            with st.expander(
                f"{medal} {candidate['name']} • {candidate['seniority_level']} • Match: {candidate['score']:.1%}",
                expanded=(i <= 3)
            ):
                # Top section: Overview metrics
                col_score, col_exp, col_skills = st.columns(3)
                
                with col_score:
                    st.metric("Overall Match", f"{candidate['score']:.1%}")
                    st.caption("🎯 Combined score")
                
                with col_exp:
                    st.metric("Seniority", candidate['seniority_level'])
                    st.caption(candidate['seniority_explanation'])
                
                with col_skills:
                    st.metric("Skill Matches", len(candidate['common_skills']))
                    st.caption(f"out of {len(candidate['explanation']['missing_critical_skills']) + len(candidate['common_skills'])} required")
                
                # Score breakdown
                st.markdown("---")
                st.subheader("📊 Score Breakdown")
                
                col_breakdown1, col_breakdown2, col_breakdown3 = st.columns(3)
                
                with col_breakdown1:
                    st.metric("Semantic Match", f"{candidate['semantic_similarity']:.1%}", help="AI-based similarity (60% weight)")
                
                with col_breakdown2:
                    st.metric("Skill Overlap", f"{candidate['skill_overlap_score']:.1%}", help="Exact skill matches (30% weight)")
                
                with col_breakdown3:
                    st.metric("Experience Match", f"{candidate['experience_match_score']:.1%}", help="Years of experience (10% weight)")
                
                # Explainability: Top Skill Contributions
                st.markdown("---")
                st.subheader("🔍 Why This Match? - Top Contributing Skills")
                
                explanation = candidate['explanation']
                
                if explanation['top_contributors']:
                    # Create a bar chart for top contributors
                    contrib_data = {
                        'Skill': [skill for skill, _ in explanation['top_contributors']],
                        'Contribution (%)': [contrib for _, contrib in explanation['top_contributors']]
                    }
                    
                    # Display as columns with progress bars
                    for skill, contribution in explanation['top_contributors']:
                        col_skill, col_bar = st.columns([1, 3])
                        with col_skill:
                            st.markdown(f"**`{skill}`**")
                        with col_bar:
                            st.progress(float(min(contribution / 100, 1.0)))
                            st.caption(f"+{contribution:.1f}% contribution")
                else:
                    st.info("No direct skill matches - score based on semantic similarity")
                
                # Missing Critical Skills
                if explanation['missing_critical_skills']:
                    st.markdown("---")
                    st.subheader("⚠️ Missing Required Skills")
                    
                    missing_skills_display = " • ".join([f"`{s}`" for s in explanation['missing_critical_skills'][:10]])
                    st.markdown(missing_skills_display)
                    
                    if len(explanation['missing_critical_skills']) > 10:
                        st.caption(f"... and {len(explanation['missing_critical_skills']) - 10} more")
                
                # Matching Skills
                st.markdown("---")
                st.subheader("✅ Matching Skills")
                if candidate['common_skills']:
                    skills_text = " • ".join([f"`{s}`" for s in candidate['common_skills']])
                    st.markdown(skills_text)
                else:
                    st.info("No exact matches, but high semantic similarity detected")
                
                # Hard vs Soft Skills
                st.markdown("---")
                st.subheader("🔧 Skill Classification")
                
                col_hard, col_soft = st.columns(2)
                
                with col_hard:
                    st.markdown("**Hard Skills (Technical)**")
                    if candidate.get('hard_skills'):
                        hard_skills_display = " • ".join([f"`{s}`" for s in candidate['hard_skills'][:10]])
                        st.markdown(hard_skills_display)
                        if len(candidate['hard_skills']) > 10:
                            st.caption(f"... and {len(candidate['hard_skills']) - 10} more")
                    else:
                        st.caption("None identified")
                
                with col_soft:
                    st.markdown("**Soft Skills (Booster)**")
                    if candidate.get('soft_skills'):
                        soft_skills_display = " • ".join([f"`{s}`" for s in candidate['soft_skills']])
                        st.markdown(soft_skills_display)
                        st.caption("Weighted 0.3x (leadership boost)")
                    else:
                        st.caption("None identified")
                
                # All Candidate Skills
                st.subheader("📋 All Candidate Skills")
                all_skills_text = " • ".join([f"`{s}`" for s in candidate['skills'][:20]])
                st.markdown(all_skills_text)
                if len(candidate['skills']) > 20:
                    st.caption(f"... and {len(candidate['skills']) - 20} more skills")
                
                # Experience breakdown (if available)
                if candidate.get('experience'):
                    st.markdown("---")
                    st.subheader("💼 Experience Profile")
                    
                    # Show top 10 skills with experience
                    exp_items = sorted(
                        candidate['experience'].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:10]
                    
                    exp_cols = st.columns(2)
                    for idx, (skill, years) in enumerate(exp_items):
                        with exp_cols[idx % 2]:
                            st.markdown(f"**`{skill}`**: {years} year{'s' if years != 1 else ''}")
                
                # Contact Information
                st.markdown("---")
                st.subheader("📧 Contact Information")
                
                # Show contact info if available
                if candidate.get('email'):
                    st.markdown(f"**Email:** {candidate['email']}")
                if candidate.get('phone'):
                    st.markdown(f"**Phone:** {candidate['phone']}")
                if not candidate.get('email') and not candidate.get('phone'):
                    st.caption("Contact information not available")
                
                # Action buttons
                st.markdown("---")
                col_action1, col_action2, col_action3 = st.columns(3)
                
                with col_action1:
                    if st.button("✅ Shortlist", key=f"shortlist_{candidate['candidate_id']}"):
                        # Track shortlist event
                        try:
                            from src.analytics import HiringFunnelAnalytics
                            analytics = HiringFunnelAnalytics()
                            
                            # Get or create search ID
                            if 'current_search_id' not in st.session_state:
                                st.session_state['current_search_id'] = analytics.track_search(
                                    job_desc,
                                    job_skills_extracted,
                                    len(results)
                                )
                            
                            analytics.track_shortlist(
                                st.session_state['current_search_id'],
                                candidate['candidate_id'],
                                candidate['score'],
                                idx + 1
                            )
                            
                            st.success(f"✅ {candidate['name']} added to shortlist!")
                        except Exception as e:
                            st.warning(f"Shortlist tracking failed: {e}")
                
                with col_action2:
                    if st.button("🎉 Mark as Hired", key=f"hire_{candidate['candidate_id']}"):
                        # Track hire event
                        try:
                            from src.analytics import HiringFunnelAnalytics
                            analytics = HiringFunnelAnalytics()
                            
                            if 'current_search_id' in st.session_state:
                                analytics.track_hire(
                                    st.session_state['current_search_id'],
                                    candidate['candidate_id'],
                                    job_skills_extracted
                                )
                                
                                st.success(f"🎉 Congratulations! {candidate['name']} has been hired!")
                                st.balloons()
                            else:
                                st.warning("Please shortlist candidate first")
                        except Exception as e:
                            st.warning(f"Hire tracking failed: {e}")
                
                with col_action3:
                    if st.button("💬 Send Feedback", key=f"feedback_{candidate['candidate_id']}"):
                        st.info("Feedback feature coming soon!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    **How it works:**
    1. Enter a job description with required skills
    2. System extracts key technical skills using NLP
    3. **New**: Experience-aware matching with multi-factor scoring:
       - 60% Semantic Similarity (BERT embeddings)
       - 30% Skill Overlap (exact matches)
       - 10% Experience Match (years of experience)
    4. **New**: Explainable AI shows which skills drive the match
    5. Returns top matches from Firebase Firestore database
    """)


def upload_resume_tab(recommender):
    """Tab for uploading new resumes - simplified version."""
    
    st.header("📤 Upload New Resumes")
    st.markdown("""
    Upload resumes in **PDF**, **DOCX**, or **TXT** format. The system will:
    1. Extract skills from the resume text
    2. Save to Firebase Firestore database
    3. Make them immediately searchable
    """)
    
    uploaded_files = st.file_uploader(
        "Choose resume files",
        type=['pdf', 'docx', 'txt'],
        accept_multiple_files=True,
        help="Upload one or more resume files"
    )
    
    if uploaded_files:
        st.info(f"📎 {len(uploaded_files)} file(s) ready to upload")
        
        if st.button("🚀 Process and Save to Firebase", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="Starting uploads...")
            success_count = 0
            duplicate_count = 0
            error_count = 0
            uploaded_names = []
            
            for i, file in enumerate(uploaded_files):
                try:
                    with st.spinner(f"Processing {file.name}..."):
                        doc_id, name, is_duplicate = recommender.add_new_resume(file, file.name)
                        
                        if is_duplicate:
                            duplicate_count += 1
                        else:
                            success_count += 1
                except Exception as e:
                    error_msg = str(e)
                    # Show errors only
                    if "corrupted or invalid" in error_msg:
                        st.error(f"❌ {file.name}: File is corrupted or invalid")
                    elif "EOF marker not found" in error_msg:
                        st.error(f"❌ {file.name}: PDF file is damaged")
                    elif len(error_msg) > 100:
                        st.error(f"❌ {file.name}: {error_msg[:100]}...")
                    else:
                        st.error(f"❌ {file.name}: {error_msg}")
                    error_count += 1
                
                progress_bar.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Processed {i + 1}/{len(uploaded_files)} files"
                )
            
            progress_bar.empty()
            
            # Show summary only
            if success_count > 0:
                st.success(f"✅ {success_count} file(s) successfully uploaded")
                st.info("� New resumes added! Switch to 'Find Candidates' tab to search them.")
            if duplicate_count > 0:
                st.warning(f"⚠️ {duplicate_count} duplicate(s) skipped")
            if error_count > 0:
                st.error(f"❌ {error_count} file(s) failed")


def analytics_dashboard_tab(recommender):
    """Analytics Dashboard with three sub-tabs: Database Insights, Model Performance, Recruiter Search Analytics."""
    
    st.header("📈 Analytics Dashboard")
    
    # Create nested tabs for different analytics views
    dash1, dash2 = st.tabs(["📊 Database Insights", "🔍 Recruiter Search Analytics"])
    
    # ----- DATABASE INSIGHTS TAB -----
    with dash1:
        st.subheader("📊 Live Database Dashboard")
        
        # Fetch analytics data (cached for 30 minutes)
        with st.spinner("Loading analytics data..."):
            analytics_data = recommender.get_analytics_data()
        
        # KPIs Row
        col1, col2 = st.columns(2)
        
        with col1:
            total_resumes = len(recommender.df) if recommender.df is not None else 0
            st.metric("📁 Total Resumes in DB", total_resumes)
        
        with col2:
            stats = recommender.get_stats()
            avg_skills = stats.get('avg_skills_per_candidate', 0.0)
            st.metric("⚡ Avg Skills per Resume", f"{avg_skills:.1f}")
        
        st.markdown("---")
        
        # Top Skills Chart
        st.subheader("🏆 Top 20 Most Common Skills in Database")
        if not analytics_data['top_skills_df'].empty:
            st.bar_chart(analytics_data['top_skills_df'])
        else:
            st.info("No skill data available yet")
    
    
    # ----- RECRUITER SEARCH ANALYTICS TAB -----
    with dash2:
        st.subheader("🔍 Recruiter Search Analytics")
        
        # Add refresh button for analytics
        col_info, col_refresh = st.columns([4, 1])
        with col_info:
            st.info("💡 **Note:** Search analytics populate as you perform candidate searches. Click 'Refresh Analytics' to see the latest data.")
        with col_refresh:
            if st.button("🔄 Refresh Analytics"):
                # Clear the search history cache
                from src.firebase_client import get_search_history
                get_search_history.clear()
                st.rerun()
        
        # Fetch analytics data
        analytics_data = recommender.get_analytics_data()
        search_history = analytics_data['search_history_df']
        
        # KPIs Row
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_searches = len(search_history) if not search_history.empty else 0
            st.metric("🔎 Total Searches Recorded", total_searches)
        
        with col2:
            unique_skills = len(analytics_data['searched_skills_df']) if not analytics_data['searched_skills_df'].empty else 0
            st.metric("🎯 Unique Skills Searched", unique_skills)
        
        with col3:
            avg_matches = 0
            if not search_history.empty and 'matching_candidates_count' in search_history.columns:
                avg_matches = search_history['matching_candidates_count'].mean()
            st.metric("👥 Avg Candidates per Search", f"{avg_matches:.1f}")
        
        st.markdown("---")
        
        # Talent Gap Analysis
        st.subheader("⚠️ Talent Gap Analysis: Supply vs Demand")
        
        if not analytics_data['skill_match_rates_df'].empty:
            st.markdown("""
            **Match Rate** = (Resumes with Skill / Total Resumes) ÷ (Searches for Skill / Total Searches)
            - **< 1.0** = Skill shortage (more demand than supply) 🔴
            - **≥ 1.0** = Sufficient supply ✅
            """)
            
            # Display the table
            st.dataframe(
                analytics_data['skill_match_rates_df'],
                use_container_width=True,
                height=400
            )
            
            # Visualize top talent gaps
            st.subheader("📊 Top Talent Gaps (Lowest Match Rates)")
            gaps_df = analytics_data['skill_match_rates_df'].head(10).set_index('Skill')
            st.bar_chart(gaps_df['Match Rate'])
            
            # Highlight critical shortages
            critical_gaps = analytics_data['skill_match_rates_df'][
                analytics_data['skill_match_rates_df']['Match Rate'] < 0.5
            ]
            
            if not critical_gaps.empty:
                st.warning(f"⚠️ **Critical Shortages Detected:** {len(critical_gaps)} skills have match rates below 0.5")
                st.dataframe(critical_gaps, use_container_width=True)
        else:
            st.info("📊 No search data available yet. Start searching for candidates to see talent gap analysis!")
        
        # Recent Searches
        if not search_history.empty:
            st.subheader("🕐 Recent Searches")
            recent_searches = search_history.sort_values('timestamp', ascending=False).head(10)
            
            for idx, row in recent_searches.iterrows():
                with st.expander(f"Search at {row['timestamp']} - {row['matching_candidates_count']} matches"):
                    st.text(row['job_description'][:500] + "..." if len(row['job_description']) > 500 else row['job_description'])


def hiring_funnel_tab(recommender):
    """Tab for hiring funnel analytics."""
    st.header("🎯 Hiring Funnel Analytics")
    st.markdown("Track candidate progression: **Search** → **Shortlist** → **Hire**")
    
    try:
        from src.analytics import HiringFunnelAnalytics
        
        # Initialize analytics
        analytics = HiringFunnelAnalytics()
        
        # Period selector
        col1, col2 = st.columns([1, 3])
        with col1:
            period = st.selectbox(
                "Analysis Period",
                [7, 30, 60, 90],
                index=1,
                format_func=lambda x: f"Last {x} days"
            )
        
        # Get metrics
        metrics = analytics.get_funnel_metrics(days=period)
        funnel_data = analytics.get_conversion_funnel_data(days=period)
        
        # Display key metrics
        st.subheader("📊 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Searches", metrics.total_searches)
        
        with col2:
            st.metric("Total Shortlists", metrics.total_shortlists)
        
        with col3:
            st.metric("Total Hires", metrics.total_hires)
        
        with col4:
            st.metric("Avg Time to Hire", f"{metrics.avg_time_to_hire_days:.1f} days")
        
        # Conversion rates
        st.subheader("📈 Conversion Rates")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Search → Shortlist",
                f"{metrics.search_to_shortlist_rate}%",
                delta=f"-{metrics.drop_off_search_to_shortlist}% drop-off",
                delta_color="inverse"
            )
        
        with col2:
            st.metric(
                "Shortlist → Hire",
                f"{metrics.shortlist_to_hire_rate}%",
                delta=f"-{metrics.drop_off_shortlist_to_hire}% drop-off",
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                "Overall Conversion",
                f"{metrics.overall_conversion_rate}%"
            )
        
        # Funnel visualization
        st.subheader("🔻 Funnel Visualization")
        
        if metrics.total_searches > 0:
            # Create funnel chart
            fig, ax = plt.subplots(figsize=(10, 6))
            
            stages = funnel_data['stages']
            counts = funnel_data['counts']
            rates = funnel_data['conversion_rates']
            
            # Horizontal bar chart (inverted funnel)
            colors = ['#4CAF50', '#FFC107', '#2196F3']
            bars = ax.barh(stages, counts, color=colors, alpha=0.7, edgecolor='black')
            
            # Add labels
            for i, (count, rate) in enumerate(zip(counts, rates)):
                ax.text(count + max(counts) * 0.02, i, 
                       f"{count} ({rate:.1f}%)", 
                       va='center', fontweight='bold')
            
            ax.set_xlabel('Number of Candidates', fontsize=12)
            ax.set_title(f'Hiring Funnel - Last {period} Days', fontsize=14, fontweight='bold')
            ax.set_xlim(0, max(counts) * 1.2)
            
            st.pyplot(fig)
        else:
            st.info("No funnel data available. Start tracking searches, shortlists, and hires!")
        
        # Time to Hire by Skill
        st.subheader("⏱️ Average Time to Hire by Skill")
        
        skill_times = analytics.get_time_to_hire_by_skill(days=period)
        
        if skill_times:
            # Create DataFrame
            df_skill_times = pd.DataFrame([
                {"Skill": skill, "Avg Days to Hire": days}
                for skill, days in list(skill_times.items())[:15]
            ])
            
            # Bar chart
            fig, ax = plt.subplots(figsize=(10, 6))
            colors_grad = plt.cm.RdYlGn_r(np.linspace(0.3, 0.9, len(df_skill_times)))
            
            ax.barh(df_skill_times['Skill'], df_skill_times['Avg Days to Hire'], 
                   color=colors_grad, edgecolor='black')
            ax.set_xlabel('Average Days to Hire', fontsize=12)
            ax.set_title('Time to Hire by Skill', fontsize=14, fontweight='bold')
            ax.invert_yaxis()
            
            st.pyplot(fig)
            
            # Table
            st.dataframe(df_skill_times, use_container_width=True, hide_index=True)
        else:
            st.info("No hire data available yet. Track hires to see skill-specific metrics!")
        
        # Manual event tracking (for demo/testing)
        with st.expander("➕ Track Hiring Events (Demo/Testing)"):
            st.markdown("**Use this to manually track events for testing:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                with st.form("track_search"):
                    st.subheader("Track Search")
                    job_desc = st.text_area("Job Description", height=100)
                    skills_input = st.text_input("Skills (comma-separated)")
                    results_count = st.number_input("Results Count", min_value=0, value=5)
                    
                    if st.form_submit_button("Track Search"):
                        skills = [s.strip() for s in skills_input.split(',') if s.strip()]
                        search_id = analytics.track_search(job_desc, skills, results_count)
                        st.success(f"✅ Tracked search: {search_id}")
                        st.session_state['last_search_id'] = search_id
            
            with col2:
                with st.form("track_hire"):
                    st.subheader("Track Hire")
                    search_id_input = st.text_input("Search ID", 
                                                   value=st.session_state.get('last_search_id', ''))
                    candidate_id = st.text_input("Candidate ID")
                    skills_required = st.text_input("Skills Required (comma-separated)")
                    
                    if st.form_submit_button("Track Hire"):
                        skills = [s.strip() for s in skills_required.split(',') if s.strip()]
                        analytics.track_hire(search_id_input, candidate_id, skills)
                        st.success("✅ Tracked hire!")
        
    except ImportError:
        st.error("Analytics module not found. Make sure src/analytics.py exists.")


def talent_gap_tab(recommender):
    """Tab for predictive talent gap forecasting."""
    st.header("🔮 Talent Gap Forecasting")
    st.markdown("**Predict skill shortages using time-series analysis of recruiter search trends**")
    
    try:
        from src.analytics import HiringFunnelAnalytics, TalentGapForecaster
        from src.report_generator import PDFReportGenerator, ExcelReportGenerator
        
        # Initialize
        analytics = HiringFunnelAnalytics()
        forecaster = TalentGapForecaster(analytics)
        
        # Settings
        col1, col2, col3 = st.columns(3)
        
        with col1:
            top_k = st.slider("Top Skills to Forecast", 5, 20, 10)
        
        with col2:
            window = st.slider("Rolling Average Window (days)", 3, 14, 7)
        
        # Get forecasts
        forecasts = forecaster.forecast_talent_gap(top_k=top_k, window=window)
        
        if forecasts:
            # Summary metrics
            st.subheader("📊 Forecast Summary")
            
            high_risk = [f for f in forecasts if f.shortage_risk == "high"]
            medium_risk = [f for f in forecasts if f.shortage_risk == "medium"]
            low_risk = [f for f in forecasts if f.shortage_risk == "low"]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "🔴 High Risk Skills",
                    len(high_risk),
                    help="Skills with high shortage risk"
                )
            
            with col2:
                st.metric(
                    "🟡 Medium Risk Skills",
                    len(medium_risk),
                    help="Skills with medium shortage risk"
                )
            
            with col3:
                st.metric(
                    "🟢 Low Risk Skills",
                    len(low_risk),
                    help="Skills with low shortage risk"
                )
            
            # Forecasts table
            st.subheader("📈 Skill Shortage Predictions (Next 30 Days)")
            
            # Create DataFrame
            df_forecasts = pd.DataFrame([
                {
                    "Skill": f.skill,
                    "Current Searches": f.current_search_count,
                    "Predicted Searches": f"{f.predicted_next_month:.1f}",
                    "Trend": f.trend.capitalize(),
                    "Shortage Risk": f.shortage_risk.upper(),
                    "Confidence": f"{int(f.confidence * 100)}%"
                }
                for f in forecasts
            ])
            
            # Color code by risk
            def highlight_risk(row):
                if row['Shortage Risk'] == 'HIGH':
                    return ['background-color: #ffcccc'] * len(row)
                elif row['Shortage Risk'] == 'MEDIUM':
                    return ['background-color: #fff4cc'] * len(row)
                else:
                    return ['background-color: #ccffcc'] * len(row)
            
            styled_df = df_forecasts.style.apply(highlight_risk, axis=1)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Trend visualization
            st.subheader("📊 Skill Search Trends")
            
            selected_skill = st.selectbox(
                "Select skill to view trend:",
                [f.skill for f in forecasts]
            )
            
            trend_data = forecaster.get_skill_trend_chart_data(selected_skill, days=90)
            
            if trend_data['dates']:
                fig, ax = plt.subplots(figsize=(12, 5))
                
                dates = pd.to_datetime(trend_data['dates'])
                counts = trend_data['counts']
                rolling_avg = trend_data['rolling_avg']
                
                ax.bar(dates, counts, alpha=0.3, label='Daily Searches', color='skyblue')
                ax.plot(dates, rolling_avg, color='darkblue', linewidth=2, 
                       label=f'{window}-day Rolling Avg', marker='o', markersize=3)
                
                ax.set_xlabel('Date', fontsize=12)
                ax.set_ylabel('Search Count', fontsize=12)
                ax.set_title(f'Search Trend: {selected_skill}', fontsize=14, fontweight='bold')
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                
                st.pyplot(fig)
            
            # Recommendations
            st.subheader("💡 Recommendations")
            
            if high_risk:
                st.error(f"**⚠️ Immediate Action Required for {len(high_risk)} Skills:**")
                st.markdown("Skills with high shortage risk:")
                for f in high_risk[:5]:
                    st.markdown(f"- **{f.skill}**: {f.current_search_count} current searches "
                              f"→ predicted {f.predicted_next_month:.0f} next month "
                              f"({f.trend} trend)")
                
                st.markdown("""
                **Recommended Actions:**
                - 🎯 Accelerate recruitment campaigns for these skills
                - 💼 Consider contractor/freelance options
                - 📚 Invest in upskilling current employees
                - 🌍 Explore remote/offshore talent pools
                - 💰 Adjust compensation packages to remain competitive
                """)
            else:
                st.success("✅ No high-risk skill shortages detected. Talent pipeline appears healthy!")
            
            # Download reports
            st.subheader("📥 Download Reports")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Generate PDF Report"):
                    with st.spinner("Generating PDF..."):
                        try:
                            funnel_metrics = analytics.get_funnel_metrics(days=30)
                            pdf_path = PDFReportGenerator.generate_talent_gap_report(
                                forecasts,
                                funnel_metrics.__dict__,
                                output_path="talent_gap_report.pdf"
                            )
                            
                            with open(pdf_path, "rb") as f:
                                st.download_button(
                                    label="⬇️ Download PDF Report",
                                    data=f,
                                    file_name="talent_gap_report.pdf",
                                    mime="application/pdf"
                                )
                            
                            st.success("✅ PDF generated successfully!")
                        except Exception as e:
                            st.error(f"PDF generation failed: {e}\nInstall: pip install reportlab")
            
            with col2:
                if st.button("📊 Generate Excel Report"):
                    with st.spinner("Generating Excel..."):
                        try:
                            funnel_metrics = analytics.get_funnel_metrics(days=30)
                            skill_times = analytics.get_time_to_hire_by_skill(days=90)
                            
                            excel_path = ExcelReportGenerator.generate_analytics_report(
                                funnel_metrics.__dict__,
                                skill_times,
                                forecasts,
                                output_path="analytics_report.xlsx"
                            )
                            
                            with open(excel_path, "rb") as f:
                                st.download_button(
                                    label="⬇️ Download Excel Report",
                                    data=f,
                                    file_name="analytics_report.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            
                            st.success("✅ Excel generated successfully!")
                        except Exception as e:
                            st.error(f"Excel generation failed: {e}\nInstall: pip install openpyxl")
        
        else:
            st.info("""
            📊 **No forecast data available yet.**
            
            The talent gap forecaster needs historical search data to make predictions.
            
            **To get started:**
            1. Use the system to search for candidates
            2. Track searches in the Hiring Funnel tab
            3. Come back here to see skill shortage predictions
            """)
    
    except ImportError as e:
        st.error(f"Analytics modules not found: {e}")


def reverse_match_tab(recommender):
    """Tab for Reverse Resume Matching."""
    st.header("🔄 Reverse Resume Matching")
    st.markdown("""
    **"What jobs is this candidate good for?"** instead of "Is this candidate good for THIS job?"
    
    🎯 **Use Cases:**
    - Internal talent redeployment
    - Career path suggestions
    - Identify versatile candidates
    - Multi-role hiring
    """)
    
    # Get candidate list
    all_resumes = get_all_resumes()
    
    if all_resumes.empty:
        st.warning("No resumes found. Upload resumes first in the 'Upload Resume' tab.")
        return
    
    # Create dropdown
    candidate_options = {f"{row.get('name', 'Unknown')} ({row.get('candidate_id', 'N/A')})": row for _, row in all_resumes.iterrows()}
    
    selected_name = st.selectbox("Select Candidate", list(candidate_options.keys()), key="reverse_match_candidate_select")
    
    top_k = st.slider("Number of role matches to show", 1, 12, 5)
    
    if st.button("🔍 Find Matching Roles", type="primary"):
        candidate = candidate_options[selected_name]
        
        # Convert Series to dict if needed
        if hasattr(candidate, 'to_dict'):
            candidate = candidate.to_dict()
        
        with st.spinner("Matching candidate to all job roles..."):
            # Initialize matcher
            matcher = ReverseResumeMatcher()
            
            # Match to all roles (pass full candidate dict)
            result = matcher.match_to_all_roles(
                candidate=candidate,
                top_k=top_k
            )
            
            # Display results
            st.success(f"✅ Matched to {len(result.role_matches)} roles!")
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Primary Match", result.primary_match.role_name)
                st.caption(f"{result.primary_match.match_score:.0%} match")
            
            with col2:
                st.metric("Redeployment Score", f"{result.redeployment_score:.1f}/5.0")
                st.caption("Versatility across roles")
            
            with col3:
                st.metric("Viable Roles", len([m for m in result.role_matches if m.match_score >= 0.6]))
                st.caption("Roles with 60%+ match")
            
            # Role matches
            st.markdown("---")
            st.subheader("🎯 Role Matches")
            
            for i, match in enumerate(result.role_matches, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
                
                with st.expander(f"{medal} {match.role_name} - {match.match_score:.0%} match", expanded=(i <= 3)):
                    # Match details
                    st.markdown(f"**Career Level:** {match.career_level}")
                    st.markdown(f"**Match Score:** {match.match_score:.0%}")
                    st.markdown(f"**Required Skills Match:** {match.required_skills_match:.0%}")
                    st.markdown(f"**Optional Skills Match:** {match.optional_skills_match:.0%}")
                    
                    # Matching skills
                    if match.matching_skills:
                        st.markdown("**✅ Matching Skills:**")
                        st.markdown(" • ".join([f"`{s}`" for s in match.matching_skills]))
                    
                    # Missing skills
                    if match.missing_required_skills:
                        st.markdown("**⚠️ Missing Required Skills:**")
                        st.markdown(" • ".join([f"`{s}`" for s in match.missing_required_skills]))
                    
                    # Learnable skills
                    if match.learnable_skills:
                        st.markdown("**📚 Could Learn (Optional Skills):**")
                        st.markdown(" • ".join([f"`{s}`" for s in match.learnable_skills]))
            
            # Career paths
            if result.suggested_career_paths:
                st.markdown("---")
                st.subheader("🚀 Suggested Career Paths")
                
                for path in result.suggested_career_paths:
                    st.markdown(f"- {path}")


def explainable_rejection_tab(recommender):
    """Tab for Explainable Rejection Reasons."""
    st.header("💬 Explainable Rejection Reasons")
    st.markdown("""
    **Transparent, ethical rejection feedback.** Instead of "Candidate rejected", show WHY + HOW to improve.
    
    🎯 **Use Cases:**
    - Candidate feedback (improve experience)
    - Talent pipeline (reconsider when skills acquired)
    - Legal compliance (defensible decisions)
    - Learning path recommendations
    """)
    
    # Get candidate list
    all_resumes = get_all_resumes()
    
    if all_resumes.empty:
        st.warning("No resumes found. Upload resumes first in the 'Upload Resume' tab.")
        return
    
    # Candidate selection
    candidate_options = {f"{row.get('name', 'Unknown')} ({row.get('candidate_id', 'N/A')})": row for _, row in all_resumes.iterrows()}
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_name = st.selectbox("Select Candidate", list(candidate_options.keys()), key="rejection_candidate_select")
    
    with col2:
        match_threshold = st.slider("Match Threshold", 0.0, 1.0, 0.65, 0.05)
    
    # Job description
    job_description = st.text_area(
        "Job Description",
        height=150,
        value="Senior DevOps Engineer\nRequired: Kubernetes, Terraform, AWS, Docker, Python, CI/CD, Monitoring"
    )
    
    required_skills = st.text_input(
        "Required Skills (comma-separated)",
        value="kubernetes, terraform, aws, docker, python, ci/cd, monitoring"
    )
    
    if st.button("📊 Generate Rejection Analysis", type="primary"):
        candidate = candidate_options[selected_name]
        
        # Convert Series to dict if needed
        if hasattr(candidate, 'to_dict'):
            candidate = candidate.to_dict()
        
        with st.spinner("Analyzing rejection reasons..."):
            # Initialize engine
            engine = ExplainableRejectionsEngine(min_match_threshold=match_threshold)
            
            # Get match score (simplified - using skill overlap)
            candidate_skills = [s.lower() for s in candidate.get('skills', [])]
            required_list = [s.strip().lower() for s in required_skills.split(',')]
            
            overlap = len(set(candidate_skills) & set(required_list))
            match_score = overlap / len(required_list) if required_list else 0.0
            
            # Generate rejection analysis
            rejection = engine.analyze_rejection(
                candidate=candidate,
                job_description=job_description,
                match_score=match_score,
                required_skills=required_list,
                candidate_skills=candidate_skills,
                experience_required=5
            )
            
            # Display formatted report
            st.markdown("---")
            report = engine.format_rejection_report(rejection)
            st.text(report)
            
            # Generate PDF
            pdf_data = generate_rejection_pdf(report, rejection.candidate_id)
            
            # Download option
            st.download_button(
                label="📄 Download Rejection Report (PDF)",
                data=pdf_data,
                file_name=f"rejection_report_{rejection.candidate_id}.pdf",
                mime="application/pdf"
            )


def market_intelligence_tab(recommender):
    """Tab for Market Intelligence Layer."""
    st.header("💰 Market Intelligence Layer")
    st.markdown("""
    **Market-aware hiring intelligence.** Understand salary pressure, skill inflation, and hiring difficulty.
    
    🎯 **Use Cases:**
    - Budget planning (know salary pressure before posting)
    - Hiring difficulty forecasting
    - Skill strategy (focus on scarce skills)
    - Competitive intelligence
    """)
    
    # Job configuration
    col1, col2 = st.columns(2)
    
    with col1:
        job_title = st.text_input("Job Title", value="Senior Backend Engineer")
    
    with col2:
        experience_level = st.selectbox(
            "Experience Level",
            ["junior", "mid", "senior", "staff", "principal"],
            index=2,
            key="market_intelligence_experience_level"
        )
    
    required_skills = st.text_input(
        "Required Skills (comma-separated)",
        value="python, golang, kubernetes, aws, terraform, docker, postgresql"
    )
    
    if st.button("📊 Generate Market Intelligence", type="primary"):
        with st.spinner("Analyzing market conditions..."):
            # Initialize engine
            engine = MarketIntelligenceEngine()
            
            # Parse skills
            skills_list = [s.strip() for s in required_skills.split(',')]
            
            # Generate report
            report = engine.analyze_market(
                job_title=job_title,
                required_skills=skills_list,
                experience_level=experience_level
            )
            
            # Display results
            st.success("✅ Market Analysis Complete!")
            
            # Salary Intelligence
            st.markdown("---")
            st.subheader("💰 Salary Intelligence")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                min_sal, max_sal = report.estimated_salary_range
                st.metric("Salary Range", f"${min_sal:,} - ${max_sal:,}")
            
            with col2:
                st.metric("Salary Drivers", len(report.salary_drivers))
                st.caption(", ".join(report.salary_drivers[:3]))
            
            with col3:
                avg_pressure = sum(sp.pressure_score for sp in report.salary_pressures) / len(report.salary_pressures)
                st.metric("Avg Salary Pressure", f"{avg_pressure:.0%}")
            
            # Top salary pressures
            st.markdown("**Top Salary Pressures:**")
            for sp in sorted(report.salary_pressures, key=lambda x: x.pressure_score, reverse=True)[:5]:
                col_skill, col_pressure, col_trend = st.columns([2, 1, 2])
                
                with col_skill:
                    st.markdown(f"**`{sp.skill}`**")
                
                with col_pressure:
                    st.progress(sp.pressure_score)
                    st.caption(f"{sp.pressure_score:.0%}")
                
                with col_trend:
                    st.caption(f"{sp.pressure_trend} • {sp.explanation}")
            
            # Skill Lifecycle
            st.markdown("---")
            st.subheader("📊 Skill Lifecycle Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🚀 Emerging Skills** (High Value)")
                if report.emerging_skills:
                    for skill in report.emerging_skills:
                        st.markdown(f"- `{skill}`")
                else:
                    st.caption("None")
            
            with col2:
                st.markdown("**💼 Commodity Skills** (Table Stakes)")
                if report.commodity_skills:
                    for skill in report.commodity_skills[:5]:
                        st.markdown(f"- `{skill}`")
                else:
                    st.caption("None")
            
            # Time to Fill
            st.markdown("---")
            st.subheader("⏰ Time-to-Fill Estimates")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Overall Difficulty", report.overall_difficulty)
            
            with col2:
                st.metric("Estimated Hiring Days", f"{report.estimated_hiring_days} days")
            
            st.markdown("**Skill-by-Skill Breakdown:**")
            for ttf in sorted(report.time_to_fills, key=lambda x: x.estimated_days, reverse=True)[:8]:
                col_skill, col_days, col_diff = st.columns([2, 1, 2])
                
                with col_skill:
                    st.markdown(f"**`{ttf.skill}`**")
                
                with col_days:
                    st.metric("Days", ttf.estimated_days)
                
                with col_diff:
                    st.caption(f"{ttf.difficulty_level} • {ttf.availability} availability")
            
            # Insights
            st.markdown("---")
            st.subheader("🔍 Key Insights")
            for insight in report.insights:
                st.info(insight)
            
            # Recommendations
            st.markdown("---")
            st.subheader("💡 Strategic Recommendations")
            for rec in report.recommendations:
                st.success(rec)
            
            # Download option
            report_text = engine.format_report(report)
            st.download_button(
                label="📄 Download Full Report",
                data=report_text,
                file_name=f"market_intelligence_{job_title.replace(' ', '_')}.txt",
                mime="text/plain"
            )


if __name__ == "__main__":
    main()


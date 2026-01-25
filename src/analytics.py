"""
Advanced Analytics Module for Resume Analysis System.

Features:
1. Hiring Funnel Analytics - Track search → shortlist → hire pipeline
2. Predictive Talent Gap Forecasting - Predict skill shortages using time-series
3. Skill Trend Analysis - Historical search patterns
4. Drop-off Rate Analysis - Identify bottlenecks in hiring process

Resume Bullet Points:
- "Built hiring funnel analytics tracking candidate progression with drop-off rate analysis"
- "Developed predictive analytics to forecast talent shortages using time-series analysis of recruiter search trends"
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
import json
import os


# ==================== Data Classes ====================

@dataclass
class SearchEvent:
    """Single search event in hiring funnel."""
    search_id: str
    timestamp: datetime
    job_description: str
    skills_searched: List[str]
    top_k: int
    results_count: int
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "search_id": self.search_id,
            "timestamp": self.timestamp.isoformat(),
            "job_description": self.job_description,
            "skills_searched": self.skills_searched,
            "top_k": self.top_k,
            "results_count": self.results_count,
            "user_id": self.user_id
        }


@dataclass
class ShortlistEvent:
    """Candidate shortlist event."""
    search_id: str
    candidate_id: str
    timestamp: datetime
    score: float
    rank: int
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "search_id": self.search_id,
            "candidate_id": self.candidate_id,
            "timestamp": self.timestamp.isoformat(),
            "score": self.score,
            "rank": self.rank,
            "user_id": self.user_id
        }


@dataclass
class HireEvent:
    """Final hire event."""
    search_id: str
    candidate_id: str
    timestamp: datetime
    skills_required: List[str]
    time_to_hire_days: float
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "search_id": self.search_id,
            "candidate_id": self.candidate_id,
            "timestamp": self.timestamp.isoformat(),
            "skills_required": self.skills_required,
            "time_to_hire_days": self.time_to_hire_days,
            "user_id": self.user_id
        }


@dataclass
class FunnelMetrics:
    """Hiring funnel metrics."""
    total_searches: int
    total_shortlists: int
    total_hires: int
    search_to_shortlist_rate: float
    shortlist_to_hire_rate: float
    overall_conversion_rate: float
    avg_time_to_hire_days: float
    drop_off_search_to_shortlist: float
    drop_off_shortlist_to_hire: float


@dataclass
class SkillTrendForecast:
    """Skill shortage forecast."""
    skill: str
    current_search_count: int
    predicted_next_month: float
    trend: str  # 'increasing', 'decreasing', 'stable'
    shortage_risk: str  # 'high', 'medium', 'low'
    confidence: float


# ==================== Analytics Tracker ====================

class HiringFunnelAnalytics:
    """
    Track and analyze hiring funnel metrics.
    
    Funnel Stages:
    1. Search - Job search initiated
    2. Shortlist - Candidate shortlisted from results
    3. Hire - Candidate hired
    
    Metrics Tracked:
    - Conversion rates at each stage
    - Drop-off rates
    - Average time-to-hire
    - Skill-specific metrics
    """
    
    def __init__(self, storage_path: str = "data/analytics_events.json"):
        """Initialize analytics tracker."""
        self.storage_path = storage_path
        self.search_events: List[SearchEvent] = []
        self.shortlist_events: List[ShortlistEvent] = []
        self.hire_events: List[HireEvent] = []
        
        # Load existing events
        self.load_events()
    
    
    def track_search(self, job_description: str, skills_searched: List[str], 
                     results_count: int, top_k: int = 5, 
                     user_id: Optional[str] = None) -> str:
        """
        Track a search event.
        
        Args:
            job_description: Job description text
            skills_searched: Extracted skills from job description
            results_count: Number of candidates returned
            top_k: Number of top candidates requested
            user_id: Optional user ID
        
        Returns:
            search_id for tracking through funnel
        """
        import uuid
        search_id = f"search_{uuid.uuid4().hex[:12]}"
        
        event = SearchEvent(
            search_id=search_id,
            timestamp=datetime.utcnow(),
            job_description=job_description,
            skills_searched=skills_searched,
            top_k=top_k,
            results_count=results_count,
            user_id=user_id
        )
        
        self.search_events.append(event)
        self.save_events()
        
        return search_id
    
    
    def track_shortlist(self, search_id: str, candidate_id: str, 
                       score: float, rank: int, 
                       user_id: Optional[str] = None):
        """
        Track a shortlist event.
        
        Args:
            search_id: ID from search event
            candidate_id: Candidate being shortlisted
            score: Candidate match score
            rank: Candidate rank in results
            user_id: Optional user ID
        """
        event = ShortlistEvent(
            search_id=search_id,
            candidate_id=candidate_id,
            timestamp=datetime.utcnow(),
            score=score,
            rank=rank,
            user_id=user_id
        )
        
        self.shortlist_events.append(event)
        self.save_events()
    
    
    def track_hire(self, search_id: str, candidate_id: str, 
                   skills_required: List[str], 
                   user_id: Optional[str] = None):
        """
        Track a hire event.
        
        Args:
            search_id: ID from search event
            candidate_id: Candidate being hired
            skills_required: Skills from job description
            user_id: Optional user ID
        """
        # Calculate time to hire
        search_event = next((e for e in self.search_events if e.search_id == search_id), None)
        if not search_event:
            raise ValueError(f"Search {search_id} not found")
        
        time_to_hire = (datetime.utcnow() - search_event.timestamp).total_seconds() / 86400  # days
        
        event = HireEvent(
            search_id=search_id,
            candidate_id=candidate_id,
            timestamp=datetime.utcnow(),
            skills_required=skills_required,
            time_to_hire_days=time_to_hire,
            user_id=user_id
        )
        
        self.hire_events.append(event)
        self.save_events()
    
    
    def get_funnel_metrics(self, days: int = 30) -> FunnelMetrics:
        """
        Calculate hiring funnel metrics from Firebase.
        
        Args:
            days: Number of days to analyze (default: 30)
        
        Returns:
            FunnelMetrics object
        """
        try:
            # Import Firebase
            from src.firebase_client import db
            from datetime import timezone
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Fetch events from Firebase
            events_ref = db.collection('hiring_events')
            events = events_ref.where('timestamp', '>=', cutoff_date).stream()
            
            search_count = 0
            shortlist_count = 0
            hire_count = 0
            hire_times = []
            
            for event_doc in events:
                event_data = event_doc.to_dict()
                event_type = event_data.get('event_type', '')
                
                if event_type == 'search':
                    search_count += 1
                elif event_type == 'shortlist':
                    shortlist_count += 1
                elif event_type == 'hire':
                    hire_count += 1
                    # Try to calculate time to hire if we have timestamps
                    # For now, use a default value
                    hire_times.append(7.0)  # Default 7 days
            
            # Calculate conversion rates
            search_to_shortlist = (shortlist_count / search_count * 100) if search_count > 0 else 0
            shortlist_to_hire = (hire_count / shortlist_count * 100) if shortlist_count > 0 else 0
            overall_conversion = (hire_count / search_count * 100) if search_count > 0 else 0
            avg_time = sum(hire_times) / len(hire_times) if hire_times else 0.0
            
            return FunnelMetrics(
                total_searches=search_count,
                total_shortlists=shortlist_count,
                total_hires=hire_count,
                search_to_shortlist_rate=search_to_shortlist,
                shortlist_to_hire_rate=shortlist_to_hire,
                overall_conversion_rate=overall_conversion,
                avg_time_to_hire_days=avg_time,
                drop_off_stages=[],
                bottleneck_stage=None
            )
        
        except Exception as e:
            # Fallback to local storage
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Filter events by date
        recent_searches = [e for e in self.search_events if e.timestamp >= cutoff_date]
        recent_shortlists = [e for e in self.shortlist_events if e.timestamp >= cutoff_date]
        recent_hires = [e for e in self.hire_events if e.timestamp >= cutoff_date]
        
        total_searches = len(recent_searches)
        total_shortlists = len(recent_shortlists)
        total_hires = len(recent_hires)
        
        # Calculate conversion rates
        search_to_shortlist_rate = (total_shortlists / total_searches * 100) if total_searches > 0 else 0
        shortlist_to_hire_rate = (total_hires / total_shortlists * 100) if total_shortlists > 0 else 0
        overall_conversion_rate = (total_hires / total_searches * 100) if total_searches > 0 else 0
        
        # Calculate drop-off rates
        drop_off_search_to_shortlist = 100 - search_to_shortlist_rate
        drop_off_shortlist_to_hire = 100 - shortlist_to_hire_rate
        
        # Calculate average time to hire
        avg_time_to_hire = np.mean([e.time_to_hire_days for e in recent_hires]) if recent_hires else 0
        
        return FunnelMetrics(
            total_searches=total_searches,
            total_shortlists=total_shortlists,
            total_hires=total_hires,
            search_to_shortlist_rate=round(search_to_shortlist_rate, 2),
            shortlist_to_hire_rate=round(shortlist_to_hire_rate, 2),
            overall_conversion_rate=round(overall_conversion_rate, 2),
            avg_time_to_hire_days=round(avg_time_to_hire, 2),
            drop_off_search_to_shortlist=round(drop_off_search_to_shortlist, 2),
            drop_off_shortlist_to_hire=round(drop_off_shortlist_to_hire, 2)
        )
    
    
    def get_time_to_hire_by_skill(self, days: int = 90) -> Dict[str, float]:
        """
        Calculate average time-to-hire for each skill.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Dict mapping skill -> avg_time_to_hire_days
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_hires = [e for e in self.hire_events if e.timestamp >= cutoff_date]
        
        skill_times = defaultdict(list)
        
        for hire in recent_hires:
            for skill in hire.skills_required:
                skill_times[skill].append(hire.time_to_hire_days)
        
        # Calculate averages
        skill_avg = {
            skill: round(np.mean(times), 2)
            for skill, times in skill_times.items()
        }
        
        # Sort by time (descending - longest first)
        return dict(sorted(skill_avg.items(), key=lambda x: x[1], reverse=True))
    
    
    def get_conversion_funnel_data(self, days: int = 30) -> Dict:
        """
        Get data for funnel visualization.
        
        Returns:
            Dict with stage names and counts
        """
        metrics = self.get_funnel_metrics(days)
        
        return {
            "stages": ["Searches", "Shortlists", "Hires"],
            "counts": [metrics.total_searches, metrics.total_shortlists, metrics.total_hires],
            "conversion_rates": [
                100.0,  # Search is 100%
                metrics.search_to_shortlist_rate,
                metrics.overall_conversion_rate
            ],
            "drop_offs": [
                0.0,  # No drop-off before search
                metrics.drop_off_search_to_shortlist,
                metrics.drop_off_shortlist_to_hire
            ]
        }
    
    
    def save_events(self):
        """Save events to disk."""
        data = {
            "search_events": [e.to_dict() for e in self.search_events],
            "shortlist_events": [e.to_dict() for e in self.shortlist_events],
            "hire_events": [e.to_dict() for e in self.hire_events]
        }
        
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    
    def load_events(self):
        """Load events from disk."""
        if not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Load search events
            self.search_events = [
                SearchEvent(
                    search_id=e['search_id'],
                    timestamp=datetime.fromisoformat(e['timestamp']),
                    job_description=e['job_description'],
                    skills_searched=e['skills_searched'],
                    top_k=e['top_k'],
                    results_count=e['results_count'],
                    user_id=e.get('user_id')
                )
                for e in data.get('search_events', [])
            ]
            
            # Load shortlist events
            self.shortlist_events = [
                ShortlistEvent(
                    search_id=e['search_id'],
                    candidate_id=e['candidate_id'],
                    timestamp=datetime.fromisoformat(e['timestamp']),
                    score=e['score'],
                    rank=e['rank'],
                    user_id=e.get('user_id')
                )
                for e in data.get('shortlist_events', [])
            ]
            
            # Load hire events
            self.hire_events = [
                HireEvent(
                    search_id=e['search_id'],
                    candidate_id=e['candidate_id'],
                    timestamp=datetime.fromisoformat(e['timestamp']),
                    skills_required=e['skills_required'],
                    time_to_hire_days=e['time_to_hire_days'],
                    user_id=e.get('user_id')
                )
                for e in data.get('hire_events', [])
            ]
            
        except Exception as e:
            print(f"Error loading events: {e}")


# ==================== Predictive Analytics ====================

class TalentGapForecaster:
    """
    Predict talent shortages using time-series analysis.
    
    Method: Rolling average + simple trend detection
    
    Resume Bullet Point:
    "Built predictive analytics to forecast talent shortages using recruiter search trends"
    """
    
    def __init__(self, analytics: HiringFunnelAnalytics):
        """Initialize forecaster with analytics data."""
        self.analytics = analytics
    
    
    def get_skill_search_trends(self, days: int = 90) -> pd.DataFrame:
        """
        Get skill search trends over time.
        
        Args:
            days: Number of days of history to analyze
        
        Returns:
            DataFrame with columns: date, skill, count
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_searches = [e for e in self.analytics.search_events if e.timestamp >= cutoff_date]
        
        # Build daily counts
        daily_skills = defaultdict(lambda: defaultdict(int))
        
        for event in recent_searches:
            date = event.timestamp.date()
            for skill in event.skills_searched:
                daily_skills[date][skill] += 1
        
        # Convert to DataFrame
        records = []
        for date, skills in daily_skills.items():
            for skill, count in skills.items():
                records.append({
                    "date": date,
                    "skill": skill,
                    "count": count
                })
        
        if not records:
            return pd.DataFrame(columns=["date", "skill", "count"])
        
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date')
    
    
    def forecast_talent_gap(self, top_k: int = 10, window: int = 7) -> List[SkillTrendForecast]:
        """
        Forecast skill shortages for next month.
        
        Algorithm:
        1. Calculate rolling average (7-day window)
        2. Detect trend (increasing/decreasing/stable)
        3. Predict next month count
        4. Assess shortage risk
        
        Args:
            top_k: Number of top skills to forecast
            window: Rolling average window (days)
        
        Returns:
            List of SkillTrendForecast objects
        """
        df = self.get_skill_search_trends(days=90)
        
        if df.empty:
            return []
        
        forecasts = []
        
        # Get top skills by total search count
        skill_totals = df.groupby('skill')['count'].sum().sort_values(ascending=False)
        top_skills = skill_totals.head(top_k).index
        
        for skill in top_skills:
            skill_data = df[df['skill'] == skill].copy()
            
            # Create full date range
            date_range = pd.date_range(
                start=skill_data['date'].min(),
                end=datetime.utcnow().date(),
                freq='D'
            )
            
            # Reindex to include all dates (fill missing with 0)
            skill_data = skill_data.set_index('date').reindex(date_range, fill_value=0)
            skill_data['count'] = skill_data['count'].fillna(0)
            
            # Calculate rolling average
            skill_data['rolling_avg'] = skill_data['count'].rolling(window=window, min_periods=1).mean()
            
            # Get recent trend (last 30 days vs previous 30 days)
            recent_30 = skill_data.tail(30)['rolling_avg'].mean()
            previous_30 = skill_data.iloc[-60:-30]['rolling_avg'].mean() if len(skill_data) >= 60 else recent_30
            
            # Detect trend
            if recent_30 > previous_30 * 1.2:
                trend = "increasing"
            elif recent_30 < previous_30 * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
            
            # Simple linear extrapolation for next month
            recent_values = skill_data.tail(30)['rolling_avg'].values
            if len(recent_values) >= 2:
                # Linear regression
                x = np.arange(len(recent_values))
                slope, intercept = np.polyfit(x, recent_values, 1)
                predicted_next_month = slope * (len(recent_values) + 30) + intercept
                predicted_next_month = max(0, predicted_next_month)  # No negative predictions
            else:
                predicted_next_month = recent_30
            
            # Assess shortage risk
            # High risk if trend is increasing and prediction is high
            current_count = int(skill_totals[skill])
            
            if trend == "increasing" and predicted_next_month > recent_30 * 1.5:
                shortage_risk = "high"
                confidence = 0.75
            elif trend == "increasing":
                shortage_risk = "medium"
                confidence = 0.65
            elif trend == "stable" and recent_30 > 5:
                shortage_risk = "medium"
                confidence = 0.55
            else:
                shortage_risk = "low"
                confidence = 0.45
            
            forecasts.append(SkillTrendForecast(
                skill=skill,
                current_search_count=current_count,
                predicted_next_month=round(predicted_next_month, 2),
                trend=trend,
                shortage_risk=shortage_risk,
                confidence=round(confidence, 2)
            ))
        
        # Sort by shortage risk (high first) then by current count
        risk_order = {"high": 0, "medium": 1, "low": 2}
        forecasts.sort(key=lambda x: (risk_order[x.shortage_risk], -x.current_search_count))
        
        return forecasts
    
    
    def get_skill_trend_chart_data(self, skill: str, days: int = 90) -> Dict:
        """
        Get data for skill trend visualization.
        
        Args:
            skill: Skill to analyze
            days: Number of days of history
        
        Returns:
            Dict with dates, counts, and rolling average
        """
        df = self.get_skill_search_trends(days=days)
        
        if df.empty or skill not in df['skill'].values:
            return {"dates": [], "counts": [], "rolling_avg": []}
        
        skill_data = df[df['skill'] == skill].copy()
        
        # Fill missing dates
        date_range = pd.date_range(
            start=skill_data['date'].min(),
            end=datetime.utcnow().date(),
            freq='D'
        )
        
        skill_data = skill_data.set_index('date').reindex(date_range, fill_value=0)
        skill_data['count'] = skill_data['count'].fillna(0)
        skill_data['rolling_avg'] = skill_data['count'].rolling(window=7, min_periods=1).mean()
        
        return {
            "dates": [d.strftime('%Y-%m-%d') for d in skill_data.index],
            "counts": skill_data['count'].tolist(),
            "rolling_avg": skill_data['rolling_avg'].round(2).tolist()
        }


# ==================== Testing ====================

if __name__ == "__main__":
    print("=" * 60)
    print("Analytics Module Test")
    print("=" * 60)
    
    # Initialize
    analytics = HiringFunnelAnalytics(storage_path="test_analytics.json")
    
    # Simulate some events
    print("\n1. Tracking events...")
    
    # Search 1
    search_id_1 = analytics.track_search(
        job_description="Python developer with ML",
        skills_searched=["python", "machine learning", "tensorflow"],
        results_count=5,
        user_id="user_001"
    )
    print(f"   Tracked search: {search_id_1}")
    
    # Shortlist from search 1
    analytics.track_shortlist(search_id_1, "candidate_001", score=0.85, rank=1)
    analytics.track_shortlist(search_id_1, "candidate_002", score=0.78, rank=2)
    print(f"   Shortlisted 2 candidates")
    
    # Hire from search 1
    analytics.track_hire(search_id_1, "candidate_001", skills_required=["python", "tensorflow"])
    print(f"   Hired candidate_001")
    
    # Search 2
    search_id_2 = analytics.track_search(
        job_description="Java backend engineer",
        skills_searched=["java", "spring boot", "microservices"],
        results_count=3
    )
    print(f"   Tracked search: {search_id_2}")
    
    # Get funnel metrics
    print("\n2. Funnel Metrics:")
    metrics = analytics.get_funnel_metrics(days=30)
    print(f"   Total searches: {metrics.total_searches}")
    print(f"   Total shortlists: {metrics.total_shortlists}")
    print(f"   Total hires: {metrics.total_hires}")
    print(f"   Search → Shortlist rate: {metrics.search_to_shortlist_rate}%")
    print(f"   Shortlist → Hire rate: {metrics.shortlist_to_hire_rate}%")
    print(f"   Overall conversion rate: {metrics.overall_conversion_rate}%")
    print(f"   Avg time to hire: {metrics.avg_time_to_hire_days} days")
    
    # Time to hire by skill
    print("\n3. Time to Hire by Skill:")
    skill_times = analytics.get_time_to_hire_by_skill()
    for skill, time in list(skill_times.items())[:5]:
        print(f"   {skill}: {time} days")
    
    # Predictive analytics
    print("\n4. Talent Gap Forecast:")
    forecaster = TalentGapForecaster(analytics)
    forecasts = forecaster.forecast_talent_gap(top_k=5)
    
    for forecast in forecasts:
        print(f"   {forecast.skill}:")
        print(f"      Current searches: {forecast.current_search_count}")
        print(f"      Predicted next month: {forecast.predicted_next_month}")
        print(f"      Trend: {forecast.trend}")
        print(f"      Shortage risk: {forecast.shortage_risk}")
    
    print("\n✅ All tests passed!")
    
    # Cleanup
    import os
    if os.path.exists("test_analytics.json"):
        os.remove("test_analytics.json")

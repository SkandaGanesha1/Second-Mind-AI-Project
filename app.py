import streamlit as st
import time
import random
import json
from datetime import datetime
from core.supervisor import SupervisorAgent
from core.storage import MemoryStorage, ContextManager
from agents.generation_agent import GenerationAgent
from agents.reflection_agent import ReflectionAgent
from agents.ranking_agent import RankingAgent
from agents.evolution_agent import EvolutionAgent
from agents.proximity_agent import ProximityAgent
from agents.meta_review_agent import MetaReviewAgent
from utils.logger import get_logger
from web.scraper import WebScraper
from web.google_search_wrapper import SearchAPI

# Initialize components
web_scraper = WebScraper()
search_api = SearchAPI()
logger = get_logger(__name__)

# Streamlit page config
st.set_page_config(
    page_title="The Second Mind | Advanced Research",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to create an advanced Perplexity-like UI
st.markdown(
    """
    <style>
        /* Main theme */
        [data-testid="stAppViewContainer"] {
            background-color: #0d1117;
            color: #e6edf3;
        }
        
        /* Header styling */
        .main-header {
            background: linear-gradient(90deg, #5e60ce, #6930c3, #7400b8);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            margin-bottom: 2rem;
            padding-top: 1rem;
        }
        
        /* Card styling */
        .research-card {
            background-color: #161b22;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #5e60ce;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .source-card {
            background-color: #1e252e;
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
            font-size: 0.9rem;
        }
        
        .confidence-high {
            color: #3fb950;
        }
        
        .confidence-medium {
            color: #f0b429;
        }
        
        .confidence-low {
            color: #f85149;
        }
        
        /* Input styling */
        [data-testid="stTextInput"] > div > div > input {
            background-color: #161b22;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 16px;
            box-shadow: none !important;
        }
        
        [data-testid="stTextInput"] > div > div > input:focus {
            border: 1px solid #5e60ce;
            box-shadow: 0 0 0 1px #5e60ce !important;
        }
        
        /* Button styling */
        .stButton > button {
            background: linear-gradient(90deg, #5e60ce, #6930c3);
            color: white;
            border-radius: 8px;
            padding: 10px 24px;
            font-weight: 600;
            border: none;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            background: linear-gradient(90deg, #6930c3, #5e60ce);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(94, 96, 206, 0.5);
        }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #161b22;
            border-radius: 8px 8px 0px 0px;
            padding: 10px 16px;
            border: none;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #5e60ce !important;
            color: white !important;
        }
        
        /* Progress bar */
        .stProgress > div > div > div > div {
            background-color: #5e60ce;
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #161b22;
            padding-top: 2rem;
        }
        
        [data-testid="stSidebarNav"] {
            padding-top: 1rem;
        }
        
        /* Citation numbers */
        .citation-number {
            background-color: #5e60ce;
            color: white;
            border-radius: 4px;
            padding: 0px 6px;
            font-size: 0.8rem;
            margin-right: 4px;
            display: inline-block;
        }
        
        /* Animated typing indicator */
        @keyframes typing {
            0% { width: 6px; }
            33% { width: 6px; margin-right: 7px; margin-left: 7px; }
            66% { width: 6px; margin-right: 7px; margin-left: 7px; }
            100% { width: 6px; }
        }
        
        .typing-indicator {
            display: flex;
            align-items: center;
            margin: 1rem 0;
        }
        
        .typing-indicator span {
            height: 6px;
            width: 6px;
            background-color: #5e60ce;
            border-radius: 50%;
            display: inline-block;
            margin: 0 2px;
            animation: typing 1.5s infinite ease-in-out;
        }
        
        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        /* Search history */
        .history-item {
            background-color: #1e252e;
            border-radius: 6px;
            padding: 10px 15px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .history-item:hover {
            background-color: #2d3440;
            transform: translateX(3px);
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Tooltip */
        .tooltip {
            position: relative;
            display: inline-block;
            border-bottom: 1px dotted #5e60ce;
            cursor: help;
        }
        
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 200px;
            background-color: #161b22;
            color: #e6edf3;
            text-align: center;
            border-radius: 6px;
            padding: 5px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
            border: 1px solid #30363d;
        }
        
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state variables
if 'research_complete' not in st.session_state:
    st.session_state.research_complete = False
if 'research_results' not in st.session_state:
    st.session_state.research_results = []
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'citations' not in st.session_state:
    st.session_state.citations = []
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Research"
if 'research_started' not in st.session_state:
    st.session_state.research_started = False
if 'live_results' not in st.session_state:
    st.session_state.live_results = []
if 'current_query' not in st.session_state:
    st.session_state.current_query = ""

# Initialize AI system
storage = MemoryStorage()
context_manager = ContextManager(storage)
supervisor = SupervisorAgent(storage, context_manager)

supervisor.register_agent("generation", GenerationAgent(web_scraper, search_api))
supervisor.register_agent("reflection", ReflectionAgent())
supervisor.register_agent("ranking", RankingAgent())
supervisor.register_agent("evolution", EvolutionAgent(web_scraper, search_api))
supervisor.register_agent("proximity", ProximityAgent(storage))
supervisor.register_agent("meta_review", MetaReviewAgent(context_manager, storage))

supervisor.start()

# Mock function to simulate citation sources
def generate_mock_citations(query):
    domains = ["nature.com", "scholar.google.com", "sciencedirect.com", "researchgate.net", 
               "ieee.org", "arxiv.org", "mit.edu", "stanford.edu", "harvard.edu"]
    
    citations = []
    num_sources = random.randint(5, 12)
    
    for i in range(num_sources):
        domain = random.choice(domains)
        year = random.randint(2018, 2024)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        
        title = f"Research on {query.split()[0:3]} and Its Applications"
        if i % 3 == 0:
            title = f"Analysis of {query.split()[0:2]} in Modern Context"
        elif i % 3 == 1:
            title = f"The Future of {query.split()[0:2]}: A Comprehensive Review"
            
        authors = ["Smith et al.", "Johnson et al.", "Zhang et al.", "Patel et al.", "Garcia et al."]
        
        citations.append({
            "id": f"cite-{i}",
            "title": title,
            "url": f"https://{domain}/article/{query.replace(' ', '-')}-{i}",
            "source": domain,
            "date": f"{year}-{month:02d}-{day:02d}",
            "authors": random.choice(authors),
            "snippet": f"This research explores the relationship between {query} and various applications in the field..."
        })
    
    return citations

# Function to simulate research
def conduct_research(query):
    # Store query in search history if it's not already there
    if query not in [item["query"] for item in st.session_state.search_history]:
        st.session_state.search_history.append({"query": query, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")})
    
    # Set current query
    st.session_state.current_query = query
    
    # Reset research state
    st.session_state.research_complete = False
    st.session_state.research_results = []
    
    # Start research
    # Update this line to actually use your GenerationAgent instead of mock data
    session_id = supervisor.start_research(query)
    st.session_state.research_started = True
    
    # Generate citations first - these will be used by the hypotheses
    st.session_state.citations = generate_mock_citations(query)
    
    # Simulate research progress with live results
    st.session_state.live_results = []
    
    # Show progress simulation
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0)
    
    # Typing indicator
    typing_indicator = st.empty()
    typing_indicator.markdown("""
    <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
        <div style="margin-left: 10px;">Researching and analyzing sources...</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Progress simulation
    for i in range(1, 11):
        progress_bar.progress(i * 10)
        
        # Add live updates
        if i == 3:
            st.session_state.live_results.append("Querying academic databases...")
        elif i == 5:
            st.session_state.live_results.append("Analyzing source reliability...")
        elif i == 7:
            st.session_state.live_results.append("Synthesizing information...")
        elif i == 9:
            st.session_state.live_results.append("Forming conclusions...")
            
        time.sleep(0.5)
    
    # Clear typing indicator when done
    typing_indicator.empty()
    
    # Here's the key part - actually get real data from your GenerationAgent
    # Instead of using sample_data
    try:
        # Get the GenerationAgent
        generation_agent = supervisor.agents.get("generation")
        if generation_agent:
            # Pass the query to the agent's generate method
            result = generation_agent.generate(query)
            
            # Check if we got valid results
            if result and isinstance(result, dict) and "results" in result and result["results"]:
                st.session_state.research_results = result["results"]
            else:
                # Fallback to sample data if something went wrong
                sample_data = {
                    'results': [
                        {
                            'id': 'hyp-1742386692-0',
                            'statement': 'AI can enhance the efficiency and security of blockchain technology.',
                            'confidence': 0.8,
                            'rationale': 'Sources suggest AI can address blockchain challenges like scalability and data management, potentially leading to more efficient and secure systems.',
                            'sources': [0, 2, 4]
                        },
                        {
                            'id': 'hyp-1742386692-1',
                            'statement': "AI can leverage blockchain's immutability and transparency to improve trust and data integrity in AI models.",
                            'confidence': 0.7,
                            'rationale': "Blockchain's inherent properties of immutability and transparency can be used to track and verify AI data and model training, potentially increasing trust and reducing bias.",
                            'sources': [1, 3]
                        },
                        {
                            'id': 'hyp-1742386692-2',
                            'statement': 'The combination of AI and blockchain can create new business opportunities and drive innovation.',
                            'confidence': 0.9,
                            'rationale': 'Sources like KPMG highlight the potential of AI and blockchain to create new business models and unlock value, particularly in areas like supply chain management and data sharing.',
                            'sources': [0, 4, 5]
                        }
                    ]
                }
                st.session_state.research_results = sample_data['results']
        else:
            # If agent not found, use sample data as fallback
            sample_data = {
                'results': [
                    {
                        'id': 'hyp-fallback-1',
                        'statement': 'Could not find GenerationAgent. This is sample data.',
                        'confidence': 0.5,
                        'rationale': 'System fallback - GenerationAgent unavailable',
                        'sources': [0, 1]
                    }
                ]
            }
            st.session_state.research_results = sample_data['results']
    except Exception as e:
        st.error(f"Error generating results: {str(e)}")
        # Use fallback data
        sample_data = {
            'results': [
                {
                    'id': 'hyp-error-1',
                    'statement': f'Error occurred: {str(e)[:50]}...',
                    'confidence': 0.3,
                    'rationale': 'System error occurred during processing',
                    'sources': [0]
                }
            ]
        }
        st.session_state.research_results = sample_data['results']
    
    # Mark research as complete
    st.session_state.research_complete = True

# Sidebar for search history
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>🧠 The Second Mind</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Search history section
    st.markdown("### 📜 Search History")
    
    if st.session_state.search_history:
        for item in reversed(st.session_state.search_history):
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(f"{item['query']}", key=f"history_{item['query']}", use_container_width=True):
                    conduct_research(item['query'])
            with col2:
                st.markdown(f"<span style='font-size: 0.8rem; color: #8b949e;'>{item['timestamp'].split()[1]}</span>", unsafe_allow_html=True)
    else:
        st.info("No search history yet")
    
    st.markdown("---")
    
    # Settings section
    with st.expander("⚙️ Settings", expanded=False):
        st.slider("Research Depth", min_value=1, max_value=10, value=7)
        st.checkbox("Use Academic Sources Only", value=False)
        st.checkbox("Include News Articles", value=True)
        st.checkbox("Enable Real-time Updates", value=True)
        st.selectbox("Time Range", ["All Time", "Past Year", "Past Month", "Past Week", "Past 24 Hours"])
        
    # About section
    with st.expander("ℹ️ About The Second Mind", expanded=False):
        st.markdown("""
        **The Second Mind** is an advanced AI research assistant that helps you gather insights and synthesize information from across the web.
        
        Our multi-agent system uses:
        - Generation AI for hypothesis formation
        - Reflection AI for critical analysis
        - Ranking AI for relevance scoring
        - Evolution AI for continuous improvement
        """)

# Main content area
st.markdown("<h1 class='main-header'>The Second Mind: AI Research Assistant</h1>", unsafe_allow_html=True)

# Create tabs
tabs = st.tabs(["🔍 Research", "📊 Insights", "📚 Sources"])

with tabs[0]:
    # Search input section
    st.markdown("### Ask a research question or enter a topic")
    
    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input("", placeholder="How can AI and blockchain technology be integrated for better security?", label_visibility="collapsed")
    with col2:
        search_button = st.button("Research", use_container_width=True)
    
    # Example suggestions
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Impact of AI on climate change", key="example1", use_container_width=True):
            conduct_research("Impact of AI on climate change")
    with col2:
        if st.button("Future of quantum computing", key="example2", use_container_width=True):
            conduct_research("Future of quantum computing")
    with col3:
        if st.button("Advancements in gene therapy", key="example3", use_container_width=True):
            conduct_research("Advancements in gene therapy")
    
    # Start research when button is clicked
    if search_button and query:
        conduct_research(query)
    
    # Display research in progress
    if st.session_state.research_started and not st.session_state.research_complete:
        st.markdown(f"### Researching: *{st.session_state.current_query}*")
        
        # Animated progress
        progress_placeholder = st.empty()
        progress_bar = progress_placeholder.progress(0)
        
        # Typing indicator
        typing_indicator = st.empty()
        typing_indicator.markdown("""
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
            <div style="margin-left: 10px;">Researching and analyzing sources...</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Progress simulation
        for i in range(1, 11):
            progress_bar.progress(i * 10)
            
            # Add live updates
            if i == 3:
                st.session_state.live_results.append("Querying academic databases...")
            elif i == 5:
                st.session_state.live_results.append("Analyzing source reliability...")
            elif i == 7:
                st.session_state.live_results.append("Synthesizing information...")
            elif i == 9:
                st.session_state.live_results.append("Forming conclusions...")
                
            time.sleep(0.5)
        
        # Clear typing indicator when done
        typing_indicator.empty()
        
        # Set research as complete
        st.session_state.research_complete = True
    
    # Display research results
    if st.session_state.research_complete:
        progress_placeholder = st.empty()
        progress_placeholder.progress(100)
        
        st.markdown(f"### Research Results: *{st.session_state.current_query}*")
        
        # Display results in cards
        for idx, item in enumerate(st.session_state.research_results):
            with st.container():
                st.markdown(f"""
                <div class="research-card">
                    <h3>{item['statement']}</h3>
                    <p>{item['rationale']}</p>
                    <div>
                """, unsafe_allow_html=True)
                
                # Display confidence with appropriate color
                conf_value = item['confidence'] * 100
                if conf_value >= 75:
                    conf_class = "confidence-high"
                elif conf_value >= 50:
                    conf_class = "confidence-medium"
                else:
                    conf_class = "confidence-low"
                
                st.markdown(f"""
                    <div style="margin-top: 15px;">
                        <span class="{conf_class}" style="font-weight: bold;">
                            Confidence: {conf_value:.1f}%
                        </span>
                    </div>
                """, unsafe_allow_html=True)
                
                # Display citation numbers
                if 'sources' in item:
                    st.markdown("<div style='margin-top: 10px;'>Sources: </div>", unsafe_allow_html=True)
                    source_html = ""
                    for source_idx in item['sources']:
                        if source_idx < len(st.session_state.citations):
                            source = st.session_state.citations[source_idx]
                            source_html += f"""
                            <span class="citation-number">{source_idx + 1}</span>
                            """
                    st.markdown(f"<div>{source_html}</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)

with tabs[1]:
    if not st.session_state.research_complete:
        st.info("Run a research query to see insights")
    else:
        st.markdown("### Key Insights & Visualizations")
        
        # Confidence distribution
        st.markdown("#### Confidence Distribution")
        confidence_data = [item['confidence'] for item in st.session_state.research_results]
        
        # Create a simple chart of confidence values
        chart_data = []
        for i, conf in enumerate(confidence_data):
            statement = st.session_state.research_results[i]['statement']
            # Truncate long statements
            if len(statement) > 40:
                statement = statement[:37] + "..."
            chart_data.append({"statement": statement, "confidence": conf * 100})
        
        # Convert to dataframe for Streamlit's charting
        import pandas as pd
        chart_df = pd.DataFrame(chart_data)
        
        # Sort by confidence
        chart_df = chart_df.sort_values(by='confidence', ascending=False)
        
        # Display bar chart
        st.bar_chart(chart_df.set_index('statement'))
        
        # Other analysis sections
        st.markdown("#### Topic Relationships")
        st.markdown("""
        <div class="research-card">
            The analysis shows strong connections between AI capabilities and blockchain security enhancements,
            with moderate connections to business applications and weaker connections to regulatory concerns.
        </div>
        """, unsafe_allow_html=True)
        
        # Consensus meter
        st.markdown("#### Research Consensus Meter")
        consensus_value = sum(confidence_data) / len(confidence_data) * 100
        st.progress(consensus_value / 100)
        st.markdown(f"""
        <div style="text-align: center; margin-top: -15px;">
            <span style="font-size: 0.9rem;">Consensus Strength: {consensus_value:.1f}%</span>
        </div>
        """, unsafe_allow_html=True)

with tabs[2]:
    if not st.session_state.research_complete:
        st.info("Run a research query to see sources")
    else:
        st.markdown("### Source Materials")
        
        # Sources filter
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            source_filter = st.selectbox("Filter by type", ["All Sources", "Academic Papers", "News Articles", "Research Reports"])
        with col2:
            sort_option = st.selectbox("Sort by", ["Relevance", "Date (Newest)", "Date (Oldest)"])
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            export_button = st.button("Export Sources", use_container_width=True)
        
        # Display sources
        for i, source in enumerate(st.session_state.citations):
            st.markdown(f"""
            <div class="source-card">
                <h4>{i+1}. {source['title']}</h4>
                <p>{source['snippet']}</p>
                <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                    <span style="color: #8b949e; font-size: 0.8rem;">{source['authors']} • {source['date']}</span>
                    <span style="color: #58a6ff; font-size: 0.8rem;">{source['source']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; margin-top: 30px; padding: 15px; border-top: 1px solid #30363d;">
    <p style="color: #8b949e; font-size: 0.9rem;">
        The Second Mind AI © 2023 | Advanced Research Platform
    </p>
</div>
""", unsafe_allow_html=True)
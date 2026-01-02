import streamlit as st
import datetime
import pandas as pd
import uuid
from typing import List, Dict

# Import specific functions from platform modules
from platforms.reddit_api import search_filtered_hot_posts
from platforms.youtube_api import search_youtube_videos

# Import specific functions from utility modules
from utils.llm_helper import get_available_models, generate_post_summary, generate_batch_summary
from utils.data_manager import save_materials, load_all_materials, get_material_by_id, delete_material
from utils.redis_helper import RedisClient

# Configure Streamlit page settings
st.set_page_config(page_title="Multi-Platform Social Media Content Filter", layout="wide", initial_sidebar_state="expanded")

# --- Logic Layer: Initialize Session State (Integrated with Redis) ---
def init_session_state():
    """
    Initialize or restore session state with unique identifier and cached data from Redis.
    Generates a UUID for the session if not exists, then loads persisted session data
    from Redis to restore user's previous state (filters, results, summaries, etc.).
    If no cached data exists, sets default values for all session state variables.
    """
    # Generate unique session ID if not present
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())  # Unique identifier for each user session
    
    # Load temporary data from Redis cache
    session_key = f"session:{st.session_state.session_id}"
    cached_session = RedisClient.get_cache(session_key)
    
    if cached_session:
        # Restore session state from Redis cache
        st.session_state.results = cached_session.get('results')
        st.session_state.post_summary = cached_session.get('post_summary', "")
        st.session_state.notes = cached_session.get('notes', "")
        st.session_state.selected_material_ids = cached_session.get('selected_material_ids', [])
        st.session_state.batch_summary = cached_session.get('batch_summary', "")
        st.session_state.time_range_days = cached_session.get('time_range_days', 7)
        st.session_state.min_upvotes = cached_session.get('min_upvotes', 50)
    else:
        # Initialize session state with default values
        if 'results' not in st.session_state:
            st.session_state.results = None
        if 'post_summary' not in st.session_state:
            st.session_state.post_summary = ""
        if 'notes' not in st.session_state:
            st.session_state.notes = ""
        if 'selected_material_ids' not in st.session_state:
            st.session_state.selected_material_ids = []
        if 'batch_summary' not in st.session_state:
            st.session_state.batch_summary = ""
        if 'time_range_days' not in st.session_state:
            st.session_state.time_range_days = 7
        if 'min_upvotes' not in st.session_state:
            st.session_state.min_upvotes = 50

def save_session_state():
    """
    Persist current session state to Redis with an expiration time.
    Packages all critical session variables (results, summaries, user inputs)
    into a dictionary and stores it in Redis with a 30-minute TTL to prevent
    stale data accumulation and ensure session persistence across page refreshes.
    """
    session_key = f"session:{st.session_state.session_id}"
    session_data = {
        'results': st.session_state.results,
        'post_summary': st.session_state.post_summary,
        'notes': st.session_state.notes,
        'selected_material_ids': st.session_state.selected_material_ids,
        'batch_summary': st.session_state.batch_summary,
        'time_range_days': st.session_state.time_range_days,
        'min_upvotes': st.session_state.min_upvotes
    }
    # Cache expires in 1800 seconds (30 minutes)
    RedisClient.set_cache(session_key, session_data, expire_seconds=1800)

# --- View Layer: Universal Post Card Renderer ---
def render_post_card(post: Dict, index: int, prefix: str = ""):
    """
    Render a standardized, platform-agnostic card for displaying social media posts/videos.
    Handles platform-specific content (YouTube video player, transcripts) and common
    elements (metadata, comments, images) with expandable sections for better UX.
    
    Args:
        post (Dict): Dictionary containing post/video metadata and content
        index (int): Index of the post in the result set (for numbering)
        prefix (str): Optional prefix for unique button keys (to avoid Streamlit key collisions)
    """
    platform = post.get('source_platform', 'reddit').lower()
    
    with st.container():
        # 1. Title and platform badge
        st.markdown(f"### {index + 1}. {post.get('title', 'No Title')}")
        
        # 2. Core metadata row
        col_m1, col_m2, col_m3, col_m4 = st.columns([1.5, 1.5, 2, 1])
        with col_m1:
            st.caption(f"Author: {post.get('author')}")
        with col_m2:
            score_label = "Views" if platform == 'youtube' else "Upvotes/Popularity"
            st.caption(f"{score_label}: {post.get('score')}")
        with col_m3:
            st.caption(f"Date: {post.get('created_date')}")
        with col_m4:
            st.markdown(f"**[{platform.upper()}]**")

        # 3. Platform-specific content rendering (YouTube video player)
        if platform == 'youtube' and post.get('video_id'):
            st.video(f"https://www.youtube.com/watch?v={post['video_id']}")
        
        # 4. Detailed content display (post body/ video description)
        if post.get('selftext'):
            with st.expander("View Detailed Description/Post Content", expanded=False):
                st.write(post.get('selftext'))

        # 5. Transcript display logic (YouTube only)
        if platform == 'youtube':
            if post.get('has_transcript'):
                with st.expander("View Video Transcript", expanded=False):
                    st.info("Below is the captured video transcript, which has been provided to AI for analysis:")
                    st.write(post.get('transcript'))
            else:
                st.caption("No available transcript found")
        
        # 6. Image display + Multimodal deep analysis
        if post.get('image_urls'):
            with st.expander(f"View Preview Images ({len(post['image_urls'])} images)", expanded=False):
                num_imgs = len(post['image_urls'])
                cols = st.columns(min(num_imgs, 3))
                for i, url in enumerate(post['image_urls'][:6]):  # Limit to 6 images for performance
                    with cols[i % 3]:
                        st.image(url, use_container_width=True)
                
                # Multimodal visual analysis button
                st.markdown("---")
                if st.button("Deep Image Intent Interpretation with OpenAI", key=f"vision_{prefix}{post.get('id', index)}"):
                    with st.spinner("Analyzing visual signals via GPT-4o..."):
                        vision_result = analyze_single_post_vision(post)
                        st.success("**AI Visual Insight Conclusion:**")
                        st.markdown(vision_result)
        
        # 7. Top comments display
        if post.get('top_comments'):
            with st.expander(f"View Top Comments ({len(post['top_comments'])})", expanded=False):
                for comment in post['top_comments']:
                    st.markdown(f"**{comment['author']}** (Upvotes {comment['score']}):")
                    st.info(comment['body'])
        
        # Link to original post
        st.markdown(f"[Go to Original Post]({post.get('permalink')})")
        st.divider()

# --- Main Application Entry Point ---
def main():
    """
    Main application workflow: initialize session state, render UI tabs,
    handle user interactions (content scraping, material management, note-taking),
    and persist state changes to Redis.
    """
    init_session_state()
    st.title("Multi-Platform Social Media Content Filter")
    
    # Create main UI tabs
    tab1, tab2, tab3 = st.tabs(["Content Scraping", "Material Library Management", "Personal Notes"])
    
    # ==================== Tab 1: Content Scraping ====================
    with tab1:
        with st.sidebar:
            st.header("1. Platform & Target")
            platform = st.selectbox("Target Platform", ["Reddit", "YouTube", "Twitter"], index=0)
            
            # Platform-specific target input
            if platform == "Reddit":
                target = st.text_input("Subreddit Name", "DestinyRising")
            elif platform == "YouTube":
                target = st.text_input("Search Keywords/Channel", "Destiny Rising")
            else:
                target = st.text_input("Search Keywords", "Destiny Rising")
            
            st.header("2. Filter Criteria")
            days = st.slider("Time Range (Past X Days)", 1, 30, st.session_state.time_range_days)
            min_score = st.number_input("Minimum Popularity/View Threshold", value=st.session_state.min_upvotes)
            
            # Real-time update of filter parameters in session state
            st.session_state.time_range_days = days
            st.session_state.min_upvotes = min_score
            
            st.markdown("---")
            st.header("3. AI-Assisted Summary")
            use_ai = st.checkbox("Auto-generate AI Summary after Scraping", value=True)
            models = get_available_models()
            selected_model = st.selectbox("Select Analysis Model", models)

        # Content scraping trigger button
        if st.button(f"Start Scraping {platform} Hot Content", type="primary"):
            with st.spinner(f"Collecting content from {platform}..."):
                # Platform-specific content scraping
                if platform == "Reddit":
                    st.session_state.results = search_filtered_hot_posts(target, days, min_score)
                elif platform == "YouTube":
                    st.session_state.results = search_youtube_videos(target, days, int(min_score))
                elif platform == "Twitter":
                    st.info("Twitter module API logic integrated (API Key configuration required)")
                    st.session_state.results = []
                
                # Trigger AI summary generation if enabled and results exist
                if use_ai and st.session_state.results:
                    st.session_state.post_summary = generate_post_summary(st.session_state.results, selected_model)
                else:
                    st.session_state.post_summary = ""
                
                # Persist updated session state to Redis
                save_session_state()

        # --- Results display logic ---
        if st.session_state.results is not None:
            if len(st.session_state.results) == 0:
                st.warning("No matching content found.")
            else:
                # 1. Save results to material library
                with st.expander("Save Results to Material Library", expanded=False):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    p_name = c1.text_input("Product Identifier", placeholder="e.g., Destiny-Competitor Analysis")
                    p_tags = c2.text_input("Tags", placeholder="Separated by commas")
                    if c3.button("Execute Save"):
                        f_params = {"platform": platform, "target": target, "days": days}
                        save_materials(
                            st.session_state.results, 
                            st.session_state.post_summary, 
                            p_name, 
                            p_tags.split(","), 
                            f_params
                        )
                        st.toast("Materials saved successfully")

                # 2. Display AI-generated summary
                if st.session_state.post_summary:
                    st.subheader("AI Viral Insight Extraction")
                    st.info(st.session_state.post_summary)

                # 3. Content view mode selection
                st.subheader(f"Total {len(st.session_state.results)} Content Items Found")
                view_mode = st.radio("Display Mode", ["Table View", "Card View"], horizontal=True)
                
                if view_mode == "Table View":
                    df = pd.DataFrame(st.session_state.results)
                    target_cols = ["title", "score", "author", "created_date", "num_comments"]
                    existing_cols = [c for c in target_cols if c in df.columns]
                    st.dataframe(df[existing_cols], use_container_width=True, hide_index=True)
                else:
                    for idx, post in enumerate(st.session_state.results):
                        render_post_card(post, idx, prefix="search_")

    # ==================== Tab 2: Material Library Management ====================
    with tab2:
        st.header("Historical Material Library")
        
        # Clear API cache button
        if st.button("Clear API Cache (Force Refresh Data)"):
            client = RedisClient()
            if client:
                client.flushdb()  # Flush current database cache
                st.success("Cache cleared successfully. Next scrape will fetch latest data.")
        
        # Load all historical materials
        all_materials = load_all_materials()
        
        if not all_materials:
            st.info("Material library is empty.")
        else:
            # Generate batch comparison report button
            if st.button("Generate Selected Materials Comparison Report"):
                if st.session_state.selected_material_ids:
                    st.session_state.batch_summary = generate_batch_summary(
                        st.session_state.selected_material_ids, 
                        selected_model, 
                        get_material_by_id
                    )
                    save_session_state()  # Persist report results to Redis
                else:
                    st.warning("Please select materials first (left checkbox).")
            
            # Display batch summary report if available
            if st.session_state.batch_summary:
                st.success("Comprehensive Research Trend Report")
                st.markdown(st.session_state.batch_summary)

            st.markdown("---")
            # Reset selected material IDs to collect fresh selections
            st.session_state.selected_material_ids = []
            for m in all_materials:
                with st.expander(f"Project: {m['product_name']} | Collection Time: {m['created_at']}"):
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        if st.checkbox("Add to Report Comparison", key=f"sel_{m['id']}"):
                            st.session_state.selected_material_ids.append(m['id'])
                    with col_b:
                        show_details = st.toggle("Expand Detailed Content", key=f"toggle_{m['id']}")
                    with col_c:
                        if st.button("Delete Record", key=f"del_{m['id']}"):
                            delete_material(m['id'])
                            st.rerun()
                    
                    # Display detailed material content if toggled
                    if show_details:
                        if m.get('summary'):
                            st.info(f"**Historical AI Analysis Summary:**\n\n{m['summary']}")
                        
                        if m['posts']:
                            st.markdown("---")
                            for idx, saved_post in enumerate(m['posts']):
                                render_post_card(saved_post, idx, prefix=f"material_{m['id']}_")
                    else:
                        # Show condensed table preview for non-expanded view
                        if m['posts']:
                            m_df = pd.DataFrame(m['posts'])
                            m_cols = [c for c in ["title", "score", "author"] if c in m_df.columns]
                            st.table(m_df[m_cols].head(5))
            
            # Persist selected material IDs to Redis
            save_session_state()

    # ==================== Tab 3: Personal Notes ====================
    with tab3:
        st.header("Personal Notes")
        st.session_state.notes = st.text_area(
            "Record your thoughts on viral content topics here...",
            value=st.session_state.notes,
            height=500
        )
        # Download notes as TXT file
        st.download_button(
            "Export Notes as TXT",
            st.session_state.notes,
            file_name=f"notes_{datetime.date.today()}.txt"
        )
        
        # Real-time persistence of notes to Redis
        save_session_state()

if __name__ == "__main__":
    main()
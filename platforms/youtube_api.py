from googleapiclient.discovery import build
import datetime
import streamlit as st
from typing import List, Dict
from config import YOUTUBE_API_KEY
from youtube_transcript_api import YouTubeTranscriptApi
from utils.redis_helper import RedisClient

def get_youtube_client():
    """
    Initialize and return a Google YouTube Data API v3 client instance.
    Uses the developer API key from the application configuration for authentication.
    """
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def get_video_transcript(video_id: str) -> Dict:
    """
    Retrieve and concatenate the transcript for a given YouTube video (with multi-language support).
    Truncates long transcripts to ensure efficient processing and storage.
    
    Args:
        video_id (str): Unique YouTube video identifier (from video URL: v=<video_id>)
    
    Returns:
        Dict: Structured transcript data with content (truncated to 2000 chars) and availability flag
    """
    try:
        # Fetch transcript with priority for Chinese variants and English
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, 
            languages=['zh-Hans', 'zh-CN', 'zh-TW', 'en']
        )
        # Concatenate transcript segments into a single text block
        full_text = " ".join([item['text'] for item in transcript_list])
        return {
            "content": full_text[:2000],  # Truncate to 2000 characters to control payload size
            "has_transcript": True
        }
    except Exception:
        # Return empty content and false flag if transcript is unavailable (no subtitles/API error)
        return {
            "content": "",
            "has_transcript": False
        }

def get_video_comments(video_id: str, limit: int = 5) -> List[Dict]:
    """
    Extract top relevant comments for a given YouTube video via the Data API.
    Returns structured comment data including author, content, and like count.
    
    Args:
        video_id (str): Unique YouTube video identifier
        limit (int, optional): Maximum number of comments to retrieve. Defaults to 5.
    
    Returns:
        List[Dict]: Structured list of top relevant comments; empty list on failure/no comments
    """
    try:
        youtube = get_youtube_client()
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=limit,
            order="relevance",  # Sort by comment relevance (instead of time) for better insights
            textFormat="plainText"
        ).execute()

        comments = []
        for item in response.get("items", []):
            snippet = item['snippet']['topLevelComment']['snippet']
            comments.append({
                "author": snippet['authorDisplayName'],
                "body": snippet['textDisplay'],
                "score": snippet.get('likeCount', 0)  # Default to 0 if like count is unavailable
            })
        return comments
    except Exception:
        # Gracefully handle API errors (e.g., comments disabled, quota exceeded)
        return []

def search_youtube_videos(query: str, days: int, min_views: int, limit: int = 20) -> List[Dict]:
    """
    Orchestrate YouTube video search, filtering, and data enrichment with caching.
    Searches for videos by query, filters by view count and publication date, enriches with
    transcripts/comments, and caches results for repeated queries.
    
    Args:
        query (str): Search keyword/phrase for YouTube video lookup
        days (int): Number of past days to filter video publication (only videos published within this range)
        min_views (int): Minimum view count required for a video to be included
        limit (int, optional): Maximum number of videos to return. Defaults to 20.
    
    Returns:
        List[Dict]: Structured list of filtered, enriched YouTube videos; empty list on failure
    """
    # Generate unique cache key based on query parameters to prevent cache collisions
    cache_key = f"youtube:{query}:{days}:{min_views}:{limit}"
    # Attempt to load cached results first for improved response speed and reduced API quota usage
    cached_data = RedisClient.get_cache(cache_key)
    if cached_data:
        st.info("Loaded data from cache to improve response speed")
        return cached_data
    
    try:
        youtube = get_youtube_client()
        # Calculate ISO 8601 formatted publication date cutoff (UTC)
        published_after = (datetime.datetime.now(datetime.timezone.utc) - 
                          datetime.timedelta(days=days)).isoformat()

        # Step 1: Search for videos matching the query and publication date range
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=limit,
            type="video",  # Restrict results to video content (exclude channels/playlists)
            publishedAfter=published_after,
            order="viewCount"  # Sort results by view count (descending) for popular content
        ).execute()

        # Extract video IDs from search results for bulk stats lookup
        video_ids = [item['id']['videoId'] for item in search_response.get("items", [])]
        if not video_ids:
            return []

        # Step 2: Retrieve bulk video statistics and details (efficient vs. single video calls)
        stats_response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids)
        ).execute()

        # Step 3: Filter videos by view count and enrich with additional data (transcripts/comments)
        filtered_videos = []
        for item in stats_response.get("items", []):
            stats = item.get('statistics', {})
            views = int(stats.get('viewCount', 0))  # Default to 0 if view count is unavailable
            
            # Skip videos that do not meet the minimum view count threshold
            if views < min_views:
                continue
            
            video_id = item['id']
            
            # Enrich video data with comments and transcript
            top_comments = get_video_comments(video_id)
            transcript_data = get_video_transcript(video_id) 

            # Structure standardized video data for application consumption
            filtered_videos.append({
                "title": item['snippet']['title'],
                "author": item['snippet']['channelTitle'],
                "score": views,  # Map view count to "score" for cross-platform consistency
                "num_comments": int(stats.get('commentCount', 0)),
                "created_date": item['snippet']['publishedAt'][:10],  # Truncate to YYYY-MM-DD
                "permalink": f"https://www.youtube.com/watch?v={video_id}",
                "selftext": item['snippet']['description'],  # Map video description to "selftext" for cross-platform consistency
                "transcript": transcript_data["content"],
                "has_transcript": transcript_data["has_transcript"],
                "image_urls": [item['snippet']['thumbnails']['high']['url']],  # High-res thumbnail for preview
                "video_id": video_id,
                "top_comments": top_comments,
                "source_platform": "youtube"
            })
        
        # Cache the enriched results to optimize future identical queries and reduce API quota usage
        RedisClient.set_cache(cache_key, filtered_videos)
        return filtered_videos
    
    except Exception as e:
        st.error(f"YouTube API exception occurred: {str(e)}")
        return []
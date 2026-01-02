import datetime
import time
import streamlit as st
from typing import List, Dict
import praw
from concurrent.futures import ThreadPoolExecutor
from config import REDDIT_APP_ID, REDDIT_APP_SECRET, REDIT_USER_AGENT
from utils.redis_helper import RedisClient

def get_reddit_instance():
    """
    Initialize and return a PRAW Reddit client instance for API interactions.
    Uses authentication credentials from the application configuration file.
    """
    return praw.Reddit(
        client_id=REDDIT_APP_ID,
        client_secret=REDDIT_APP_SECRET,
        user_agent=REDIT_USER_AGENT
    )

def crawl_with_strategy(subreddit, sort_type, time_filter, cutoff_date, min_upvotes, limit):
    """
    Execute a targeted crawling strategy for a specific subreddit with pagination, filtering,
    and rate limiting. Collects posts that meet the minimum upvote threshold and date cutoff.
    
    Args:
        subreddit: PRAW Subreddit instance to crawl
        sort_type (str): Post sorting method ("top", "hot", "new")
        time_filter (str, optional): Time filter for "top" sorting (e.g., "day", "week", "month")
        cutoff_date (datetime.datetime): UTC datetime cutoff for post creation (no posts older than this)
        min_upvotes (int): Minimum upvote score required for a post to be included
        limit (int): Maximum number of valid posts to collect
    
    Returns:
        List[Dict]: List of structured post dictionaries meeting all filtering criteria
    """
    batch_posts = []
    after = None  # Pagination marker for Reddit API (continue after last post in current batch)
    safety_counter = 0  # Prevent infinite loops with maximum iteration cap
    max_iterations = 60 if min_upvotes <= 50 else 30  # Adjust iteration cap based on filter strictness
    no_valid_count = 0  # Track consecutive batches with no valid posts
    max_no_valid = 6 if min_upvotes <= 50 else 5  # Adjust fail cap based on filter strictness

    # Main crawling loop with pagination and safety guards
    while len(batch_posts) < limit and safety_counter < max_iterations and no_valid_count < max_no_valid:
        safety_counter += 1
        remaining = limit - len(batch_posts)
        current_limit = min(100, remaining)  # Reddit API maxes out at 100 posts per request
        
        # Fetch batch of posts from Reddit API with current pagination
        posts = []
        try:
            if sort_type == "top" and time_filter:
                posts = list(subreddit.top(time_filter, limit=current_limit, params={"after": after}))
            elif sort_type == "hot":
                posts = list(subreddit.hot(limit=current_limit, params={"after": after}))
            else:
                posts = list(subreddit.new(limit=current_limit, params={"after": after}))
        except Exception:
            posts = []  # Gracefully handle API request failures
        
        # Handle empty batch (rate limit or no posts available)
        if not posts:
            no_valid_count += 1
            sleep_time = 0.7 if min_upvotes <= 50 else 1.2  # Adjust rate limit based on filter strictness
            time.sleep(sleep_time)
            continue
        
        batch_has_valid = False
        batch_oldest = None  # Track oldest post in current batch to detect cutoff crossing
        
        # Process each post in the current batch
        for post in posts:
            post_created = datetime.datetime.fromtimestamp(post.created_utc, datetime.timezone.utc)
            batch_oldest = post_created if not batch_oldest else min(batch_oldest, post_created)
            
            # Filter posts by creation date and minimum upvote threshold
            if post_created >= cutoff_date:
                if post.score >= min_upvotes:
                    # Structure post data into standardized dictionary
                    post_data = {
                        "id": post.id,
                        "title": post.title,
                        "author": str(post.author) if post.author else "Unknown Author",
                        "score": post.score,
                        "created_utc": post.created_utc,
                        "created_date": post_created.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        # Post content fields
                        "selftext": post.selftext,
                        "selftext_preview": post.selftext[:200] + "..." if post.selftext else "",
                        # Original post link
                        "permalink": f"https://www.reddit.com{post.permalink}",
                        # Image URLs attached to post
                        "image_urls": extract_image_urls(post),
                        # Comment metrics
                        "num_comments": post.num_comments,
                        # Top user comments for the post
                        "top_comments": get_top_comments(post, limit=10),
                        # Platform source identifier
                        "source_platform": "reddit"
                    }
                    batch_posts.append(post_data)
                batch_has_valid = True
            else:
                # Exit early if oldest post in batch is beyond cutoff date
                if batch_oldest < cutoff_date:
                    break
        
        # Update no-valid counter based on batch results
        if not batch_has_valid:
            no_valid_count += 1
        else:
            no_valid_count = 0
        
        # Update pagination marker for next batch
        after = posts[-1].name if posts else None
        # Enforce rate limiting to avoid hitting Reddit API limits
        sleep_time = 0.7 if min_upvotes <= 50 else 1.2
        time.sleep(sleep_time)
    
    return batch_posts

def search_filtered_hot_posts(
    subreddit_name: str, 
    time_range_days: int, 
    min_upvotes: int, 
    limit: int = 500
) -> List[Dict]:
    """
    Orchestrate multi-strategy Reddit post crawling with caching, deduplication, and result sorting.
    Uses Redis caching to improve response times for repeated queries and parallel execution
    of multiple crawling strategies for comprehensive results.
    
    Args:
        subreddit_name (str): Name of the target Reddit subreddit (without r/)
        time_range_days (int): Number of past days to filter posts (1, 7, 30, or custom)
        min_upvotes (int): Minimum upvote score required for posts to be included
        limit (int, optional): Maximum number of posts to return. Defaults to 500.
    
    Returns:
        List[Dict]: Sorted list of structured, filtered Reddit posts; empty list on failure
    """
    # Generate unique cache key based on query parameters (prevents cache collisions)
    cache_key = f"reddit:{subreddit_name}:{time_range_days}:{min_upvotes}:{limit}"
    # Attempt to retrieve cached results first for performance optimization
    cached_data = RedisClient.get_cache(cache_key)
    if cached_data:
        st.info("Loaded data from cache to improve response speed")
        return cached_data
    
    try:
        reddit = get_reddit_instance()
        subreddit = reddit.subreddit(subreddit_name)
        # Calculate UTC cutoff date based on requested time range
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=time_range_days)
        print(f"Filter Parameters - Time Range: {time_range_days} days, Cutoff Date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Use dictionary for deduplication (post ID as key)
        all_posts = {}
        sort_strategies = []
        
        # Define crawling strategies based on time range for optimal results
        if time_range_days == 30:
            sort_strategies = [
                ("top", "month"),
                ("hot", None),
                ("new", None)
            ]
        else:
            if time_range_days in [1, 7]:
                sort_method = {1: "day", 7: "week"}[time_range_days]
                sort_strategies = [("top", sort_method)]
            else:
                sort_strategies = [("new", None)]
        
        # Execute multiple crawling strategies in parallel for efficiency
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_strategy = {}
            for sort_type, time_filter in sort_strategies:
                future = executor.submit(
                    crawl_with_strategy,
                    subreddit, sort_type, time_filter, cutoff_date, min_upvotes, limit
                )
                future_to_strategy[future] = (sort_type, time_filter)
            
            # Collect and deduplicate results from all parallel strategies
            for future in future_to_strategy:
                batch_posts = future.result()
                for post in batch_posts:
                    if post["id"] not in all_posts:
                        all_posts[post["id"]] = post
        
        # Convert deduplicated posts to list and sort by upvote score (descending)
        candidate_posts = list(all_posts.values())
        candidate_posts = sorted(candidate_posts, key=lambda x: x["score"], reverse=True)
        
        # Truncate results to meet the requested limit
        if len(candidate_posts) > limit:
            candidate_posts = candidate_posts[:limit]

        # Log result statistics for debugging and monitoring
        if candidate_posts:
            earliest = min(p["created_date"] for p in candidate_posts)
            latest = max(p["created_date"] for p in candidate_posts)
            min_score = min(p["score"] for p in candidate_posts)
            max_score = max(p["score"] for p in candidate_posts)
            print(f"Result Statistics - Total: {len(candidate_posts)}, Min Upvotes: {min_score}, Max Upvotes: {max_score}")
            print(f"Time Coverage - Earliest: {earliest}, Latest: {latest}")
        else:
            print(f"No qualifying content found (Time Range: {time_range_days} days, Minimum Upvotes: {min_upvotes})")
        
        # Cache results to optimize future identical queries
        RedisClient.set_cache(cache_key, candidate_posts)
        return candidate_posts
    
    except Exception as e:
        st.error(f"Crawling failed: {str(e)}")
        return []

def get_top_comments(post, limit: int = 10) -> List[Dict]:
    """
    Extract and structure the top-voted comments for a given Reddit post (sorted by score).
    Skips nested comments (via replace_more) to improve performance and reduce API calls.
    
    Args:
        post: PRAW Post instance to extract comments from
        limit (int, optional): Maximum number of top comments to return. Defaults to 10.
    
    Returns:
        List[Dict]: Structured list of top comments; empty list on failure
    """
    try:
        # Replace more comment placeholders with actual comments (0 = no nested comments)
        post.comments.replace_more(limit=0)
        top_comments = []
        # Sort comments by upvote score (descending) and take top N
        for comment in sorted(post.comments, key=lambda c: c.score, reverse=True)[:limit]:
            comment_created = datetime.datetime.fromtimestamp(comment.created_utc, datetime.timezone.utc)
            top_comments.append({
                "author": str(comment.author) if comment.author else "Unknown User",
                "score": comment.score,
                "body": comment.body,
                "created_date": comment_created.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "is_stickied": comment.stickied
            })
        return top_comments
    except Exception:
        return []

def extract_image_urls(post) -> List[str]:
    """
    Extract direct image URLs and Imgur gallery links from a Reddit post.
    Identifies common image file extensions and Imgur gallery patterns for reliable extraction.
    
    Args:
        post: PRAW Post instance to extract image URLs from
    
    Returns:
        List[str]: List of valid image/gallery URLs; empty list if no images found
    """
    image_urls = []
    if hasattr(post, "url") and post.url:
        # Check for direct image file URLs
        image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
        if any(post.url.endswith(ext) for ext in image_extensions):
            image_urls.append(post.url)
        # Check for Imgur gallery/album URLs
        elif "imgur.com/a/" in post.url or "imgur.com/gallery/" in post.url:
            image_urls.append(post.url)
    return image_urls
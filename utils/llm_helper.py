import streamlit as st
from openai import OpenAI
from typing import List, Dict
from config import DEEPSEEK_API_KEY, OPENAI_API_KEY, ZHIPU_API_KEY  # Add Zhipu API key import

def get_deepseek_client():
    """
    Initialize and return a Deepseek LLM client using OpenAI-compatible interface.
    Configures the official Deepseek API base URL and authentication key.
    """
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

def get_openai_client():
    """
    Initialize and return an official OpenAI LLM client (primarily for multimodal vision analysis).
    Uses the official OpenAI API endpoint and authentication key.
    """
    return OpenAI(api_key=OPENAI_API_KEY)

# Add Zhipu client initialization function
def get_zhipu_client():
    """
    Initialize and return a Zhipu (GLM) LLM client using OpenAI-compatible interface.
    Configures the official Zhipu Big Model API base URL and authentication key.
    """
    return OpenAI(
        api_key=ZHIPU_API_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4"  # Zhipu API base endpoint
    )

def get_available_models() -> List[str]:
    """
    Retrieve the list of supported LLM models for content analysis and summary generation.
    Includes models from Deepseek, OpenAI, and Zhipu (GLM) ecosystems.
    
    Returns:
        List[str]: Sorted list of supported model identifiers (API-compatible)
    """
    return ["deepseek-chat", "deepseek-reasoner", "gpt-4o", "gpt-4o-mini", "glm-4", "glm-3-turbo"]

def analyze_single_post_vision(post: Dict) -> str:
    """
    Perform multimodal vision analysis on a social media post with attached images using GPT-4o-mini.
    Combines post text (title/body) and image content to generate actionable insights for content creation.
    
    Args:
        post (Dict): Social media post dictionary containing image URLs and text metadata
    
    Returns:
        str: AI-generated vision analysis report or error message if analysis fails
    """
    if not post.get('image_urls'):
        return "This post contains no images for visual analysis."
    
    client = get_openai_client()
    
    # Construct vision analysis prompt (game trend expert persona)
    prompt = f"""
    As a game trend expert, please analyze the content of the attached images.
    Post Title: {post['title']}
    Post Body: {post.get('selftext', 'No body content available')}
    
    Please answer the following questions by combining the images and text content:
    1. What is the core message conveyed by the images? (e.g., showing in-game gear, reporting a bug, level screenshot, meme reference)
    2. Why would this visual content attract players to click and engage?
    3. What visual presentation suggestions would you give if I want to create similar high-engagement content?
    """
    
    # Build multimodal content payload (text + images)
    content = [{"type": "text", "text": prompt}]
    for url in post['image_urls'][:3]:  # Limit to first 3 images for performance and cost optimization
        content.append({
            "type": "image_url",
            "image_url": {"url": url}
        })

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Optimal cost-performance ratio for visual analysis tasks
            messages=[{"role": "user", "content": content}],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Visual analysis failed: {str(e)}"

def generate_post_summary(posts: List[Dict], model_name: str) -> str:
    """
    Core analysis: Automatically switch between text-only modes for different LLM providers
    (OpenAI/GPT, Zhipu/GLM, Deepseek) based on the selected model. Generates a comprehensive
    social media content strategy report from scraped posts.
    
    Args:
        posts (List[Dict]): List of scraped social media posts with metadata and user comments
        model_name (str): Identifier of the selected LLM model for summary generation
    
    Returns:
        str: AI-generated content strategy report or error message if generation fails
    """
    if not posts:
        return ""
    
    # Determine LLM provider based on model name keyword
    is_openai = "gpt" in model_name
    is_zhipu = "glm" in model_name
    client = get_openai_client() if is_openai else get_zhipu_client() if is_zhipu else get_deepseek_client()
    
    content_parts = []
    for p in posts[:15]:  # Limit to first 15 posts to avoid token overflow
        part = f"[Title]: {p['title']}\n"
        if p.get('selftext'):
            part += f"[Content Description]: {p['selftext'][:500]}\n"  # Truncate long bodies to control token count
        
        if p.get('top_comments'):
            comments = " || ".join([f"{c['author']}(Upvotes {c['score']}): {c['body']}" for c in p['top_comments'][:5]])
            part += f"[Community Feedback]: {comments}\n"
        
        # Note image presence for OpenAI models (batch summary focuses on text primarily)
        if is_openai and p.get('image_urls'):
            part += f"[Visual Attachments]: Contains {len(p['image_urls'])} images\n"
            
        content_parts.append(part)
    
    all_content = "\n---\n".join(content_parts)
    
    # Construct prompt for Reddit-focused social media content strategy
    prompt = f"""
    You are a viral content strategist with deep expertise in Reddit gaming community culture and propagation rules.
    You have a precise understanding of Reddit user preferences and the interaction dynamics of various game subreddits.

    Based on the collected player discussion content below, dig deep into the core demands and emotional pain points,
    extract key elements that can drive viral traffic, and output a Reddit-adapted content creation strategy report
    with the following requirements:
    1.  Content Summary: Clearly sort out the core topics of current player discussions (mark which post they come from),
        the key event context, appropriately quote key expressions from the original text, and clarify the core player
        groups covered (e.g., core paying players, casual casual players).
    2.  Traffic Signal Light: Precisely locate the core contradictions/excitement points with the most intense community emotions,
        must cite high-interaction comment originals as support, and mark the emotional tendency (anger/disappointment/excitement, etc.)
        and possible interaction directions.
    3.  Viral Topic Library (3 proposals): Combine Reddit's viral logic (e.g., questions, resonant topics, viewpoint alignment, etc.),
        design 4 directly publishable post topics, each topic must clarify the adapted subreddit direction and core interaction hooks
        to stimulate large-scale follow-up discussions.
    4.  Viral Comment Memes/Golden Sentences Extraction: Excerpt the most communicable player complaints and emotional golden sentences,
        mark their applicable scenarios (e.g., title eye-catching, comment section interaction, copy secondary creation),
        and prioritize concise, powerful expressions that are easy to trigger imitation.

    Scraped Content Below:
    {all_content}
    """

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a practical social media marketing expert, adept at converting community discussions into high-traffic creative ideas."},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        error_msg = str(e)
        if "402" in error_msg:
            return "Insufficient balance, please check your account."
        return f"Analysis failed: {error_msg}"

def generate_batch_summary(material_ids: List[str], model_name: str, get_material_fn) -> str:
    """
    Generate a cross-material comparative trend report by aggregating multiple historical material batches.
    Identifies evergreen topics and provides serialized content recommendations for long-term community operation.
    
    Args:
        material_ids (List[str]): List of unique material UUIDs to include in the batch analysis
        model_name (str): Identifier of the selected LLM model for report generation
        get_material_fn: Callback function to retrieve material details by ID (from data manager)
    
    Returns:
        str: AI-generated comparative trend report or error message if generation fails
    """
    if not material_ids:
        return ""
        
    # Determine LLM provider based on model name keyword
    is_openai = "gpt" in model_name
    is_zhipu = "glm" in model_name
    client = get_openai_client() if is_openai else get_zhipu_client() if is_zhipu else get_deepseek_client()
    
    combined_context = ""
    
    for m_id in material_ids:
        material = get_material_fn(m_id)
        if material:
            combined_context += f"\nResearch Batch: {material['product_name']} ({material['created_at']})\n"
            titles = [p['title'] for p in material['posts'][:10]]
            combined_context += "Popular Title Collection: " + " / ".join(titles) + "\n"

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a gaming industry trend analyst with expertise in identifying long-term community topics."},
                {"role": "user", "content": f"Analyze the multiple sets of research results below, identify 'evergreen topics', and provide serialized content recommendations:\n{combined_context}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Report generation failed: {str(e)}"
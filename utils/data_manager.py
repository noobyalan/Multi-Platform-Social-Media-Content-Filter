import mysql.connector
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from config import DB_CONFIG

# Database Connection Utility Functions
def get_db_connection():
    """Establish and return a MySQL database connection using config parameters."""
    return mysql.connector.connect(**DB_CONFIG)

def save_materials(
    posts: List[Dict],
    summary: str,
    product_name: str,
    tags: List[str],
    fetch_params: Dict
) -> str:
    """
    Persist social media materials to the MySQL database.
    Converts complex data structures (lists/dicts) to JSON strings for storage,
    handles tag formatting, and ensures atomicity with commit/rollback logic.
    
    Args:
        posts (List[Dict]): List of scraped social media posts/videos with metadata
        summary (str): AI-generated summary for the collected materials
        product_name (str): Unique identifier for the product/project related to the materials
        tags (List[str]): List of descriptive tags for categorization and filtering
        fetch_params (Dict): Dictionary of scraping parameters (platform, target, time range, etc.)
    
    Returns:
        str: Unique UUID of the saved material record (for future retrieval/updates)
    """
    material_id = str(uuid.uuid4())
    connection = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert query with raw_data field to store structured supplementary data
        query = """
        INSERT INTO materials 
        (id, product_name, tags, platform, target, fetch_params, ai_summary, posts, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # Convert tag list to comma-separated string for simplified database storage
        tags_str = ','.join(tags) if tags else ''
        
        # Serialize complex data to JSON strings (preserve non-ASCII characters)
        fetch_params_json = json.dumps(fetch_params, ensure_ascii=False)
        posts_json = json.dumps(posts, ensure_ascii=False)
        # Use empty JSON object for raw_data instead of empty string to avoid JSON parsing errors
        raw_data = '{}'
        
        # Execute parameterized query to prevent SQL injection
        cursor.execute(query, (
            material_id,
            product_name,
            tags_str,
            fetch_params.get('platform', ''),
            fetch_params.get('target', ''),
            fetch_params_json,
            summary,
            posts_json,
            raw_data
        ))
        
        connection.commit()
        return material_id
        
    except mysql.connector.Error as err:
        print(f"Database error occurred: {err}")
        if connection:
            connection.rollback()  # Revert changes on transaction failure
        raise
    finally:
        if connection:
            connection.close()  # Ensure connection closure to prevent resource leaks

def load_all_materials() -> List[Dict]:
    """
    Retrieve all material records from the MySQL database, sorted by creation time (newest first).
    Deserializes JSON-encoded fields back to native Python data structures for application usage.
    
    Returns:
        List[Dict]: List of material dictionaries with parsed nested data; empty list on error
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)  # Return results as dictionaries for readability
        
        query = "SELECT * FROM materials ORDER BY created_at DESC"
        cursor.execute(query)
        
        materials = cursor.fetchall()
        
        # Deserialize JSON fields and format tags for application consumption
        for material in materials:
            if material['fetch_params']:
                material['fetch_params'] = json.loads(material['fetch_params'])
            if material['posts']:
                material['posts'] = json.loads(material['posts'])
            if material['tags']:
                material['tags'] = material['tags'].split(',')
            # Parse raw_data JSON string back to dictionary
            if material['raw_data']:
                material['raw_data'] = json.loads(material['raw_data'])
        
        return materials
        
    except mysql.connector.Error as err:
        print(f"Database error occurred: {err}")
        return []
    finally:
        if connection:
            connection.close()

def get_material_by_id(material_id: str) -> Optional[Dict]:
    """
    Retrieve a single material record from the database by its unique UUID.
    Deserializes JSON-encoded fields to restore the original data structure.
    
    Args:
        material_id (str): Unique UUID of the material record to retrieve
    
    Returns:
        Optional[Dict]: Material dictionary with parsed nested data if found; None otherwise (or on error)
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM materials WHERE id = %s"
        cursor.execute(query, (material_id,))
        material = cursor.fetchone()
        
        # Deserialize complex fields if record exists
        if material:
            if material['fetch_params']:
                material['fetch_params'] = json.loads(material['fetch_params'])
            if material['posts']:
                material['posts'] = json.loads(material['posts'])
            if material['tags']:
                material['tags'] = material['tags'].split(',')
            # Parse raw_data JSON string back to dictionary
            if material['raw_data']:
                material['raw_data'] = json.loads(material['raw_data'])
        
        return material
        
    except mysql.connector.Error as err:
        print(f"Database error occurred: {err}")
        return None
    finally:
        if connection:
            connection.close()

def delete_material(material_id: str) -> bool:
    """
    Delete a material record from the database by its unique UUID.
    Ensures transactional integrity with commit/rollback on failure.
    
    Args:
        material_id (str): Unique UUID of the material record to delete
    
    Returns:
        bool: True if the record was successfully deleted (row count > 0); False otherwise (or on error)
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = "DELETE FROM materials WHERE id = %s"
        cursor.execute(query, (material_id,))
        connection.commit()
        
        # Return True only if at least one row was affected (record existed and was deleted)
        return cursor.rowcount > 0
        
    except mysql.connector.Error as err:
        print(f"Database error occurred: {err}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()
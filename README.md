# Multi-Platform Social Media Content Filter

## Project Overview

This project is a **Streamlit-based multi-platform social media content collection and analysis system** designed to help users efficiently discover, filter, analyze, and organize high-impact content from platforms such as **Reddit** and **YouTube**.

The system integrates **data scraping, structured Mysql storage, Redis-based session persistence, and Large Language Models (LLMs)** to automatically generate insights and comparative analyses. It is suitable for **market research, competitor analysis, trend discovery, and content ideation**.

Core objectives:

* Cross-platform hot content scraping (Reddit / YouTube)
* Time-based and popularity-based filtering
* LLM-powered automatic summaries and trend insights
* Persistent material library with comparison reports
* Session recovery and caching via Redis

---

## Key Features

### 1. Content Scraping

* **Reddit**: Collects hot posts from a specified subreddit with filters on time range and minimum upvotes
* **YouTube**: Searches videos by keyword or channel, retrieves metadata, descriptions, and transcripts (if available)

### 2. AI-Powered Analysis

* Supports multiple LLM backends (OpenAI, Gemini, DeepSeek, Zhipu, etc.)
* Automatically generates:

  * High-level summaries and viral signal extraction for a single scraping task
  * Cross-project comparative reports across multiple saved materials
* YouTube videos support **transcript-level semantic analysis**
* Image-based posts support **multimodal visual intent analysis** (OpenAI Vision)

### 3. Material Library Management

* Scraped results can be saved as **project-level materials** in Mysql database
* Each material includes:

  * Scraping parameters
  * Raw post/video data
  * AI-generated summaries
* Supports:

  * Deletion of historical records
  * Multi-material selection for **trend comparison reports**

### 4. Session & Cache Management

* Uses **Redis** to persist session state
* Automatically restores after page refresh:

  * Scraping results
  * AI summaries
  * Filter parameters
  * User selections
* API cache can be cleared manually to force fresh data retrieval

### 5. Personal Notes

* Built-in note editor for recording research insights
* One-click export to `.txt`

---

## Requirements

### 1. Python Version

```bash
Python >= 3.9
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

(Core dependencies include `streamlit`, `pandas`, `redis`, `python-dotenv`, and platform-specific SDKs.)

---

## Configuration

### 1. Environment Variables (.env)

All sensitive information must be stored in environment variables and must NOT be hard-coded in the source code. This includes:All sensitive information must be stored in environment variables and must NOT be hard-coded in the source code. This includes:
* Reddit API
* YouTube Data API
* OpenAI / Gemini / DeepSeek / Zhipu
* Database credentials
* Redis connection settings
---

## How to Use

### 1. Launch the Application

```bash
streamlit run main.py
```

The web interface will open automatically in your browser.

---

### 2. Scraping Workflow

1. Select the target platform (Reddit / YouTube)
2. Enter the target (subreddit name or search keywords)
3. Configure time range and minimum popularity threshold
4. Enable or disable AI auto-summary and select an LLM model
5. Click **Start Scraping**

---

### 3. Saving & Analyzing Materials

* Save scraping results as a named project
* In **Material Library**:

  * Select multiple projects
  * Generate a cross-project comparison and trend analysis report

---

### 4. Notes & Export

* Record insights in **Personal Notes**
* Export notes as a TXT file with one click

---

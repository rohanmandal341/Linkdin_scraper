

# LinkedIn Scraper (Google CSE–Based)

## Purpose

This service extracts **structured public LinkedIn profile data** (name, headline, location, experience, education) using **Google-indexed content**, without scraping LinkedIn or using browser automation.

The approach is designed to be:

* Stable
* Ban-safe
* Cost-efficient
* Deterministic (no AI)

---

## Why This Approach Works

* Google already indexes public LinkedIn profiles
* Google Custom Search API provides **official JSON access**
* Avoids LinkedIn / Google bot detection
* No Playwright / Selenium / proxies required
* Rule-based parsing ensures predictable output

This trades **completeness** for **reliability and scale**.

---

## Tech Stack

* Python
* FastAPI
* Google Custom Search API
* Regex + heuristics (no AI)

---

## Project Structure

```
linkedin/
├── linkedin.py        # FastAPI service
├── requirements.txt  # Dependencies
├── .env               # Environment variables
└── README.md
```

---

## Environment Variables

Create a `.env` file:

```env
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id
```

* `GOOGLE_API_KEY`: authenticates requests
* `GOOGLE_CSE_ID`: defines the search engine configuration

---

## Install & Run

```bash
pip install -r requirements.txt
uvicorn linkedin:app --reload
```

Swagger UI:

```
http://127.0.0.1:8000/docs
```

---

## API Endpoint

### POST `/extract`

**Input**

```json
{
  "linkedin_url": "https://www.linkedin.com/in/username/"
}
```

**Output**


```json
{
  "status": "public_structured",
  "confidence": 0.9,
  "raw_google_data": {
    "title": "John Doe - Software Engineer | LinkedIn",
    "snippet": "Hi, I'm John, a software engineer based in Bangalore with experience in backend development... · Experience: ABC Technologies · Education: XYZ University",
    "url": "https://www.linkedin.com/in/john-doe-123456/"
  },
  "structured_data": {
    "name": "John Doe",
    "headline": "software engineer",
    "about": "Hi, I'm John, a software engineer based in Bangalore with experience in backend development...",
    "location": "Bangalore",
    "experience": "ABC Technologies",
    "education": "XYZ University"
  }
}

```

---

## Notes / Limitations

* Only Google-indexed public data is available
* No access to private profiles or Google UI panels
* Average response time ~1–1.3s (Google API latency)

---

### Summary

This is a **production-safe LinkedIn enrichment service** that prioritizes **stability, legality, and cost** over aggressive scraping.

---

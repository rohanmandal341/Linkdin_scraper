import os
import re
import requests
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# ------------------ SETUP ------------------

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
    raise RuntimeError("Missing Google environment variables")

app = FastAPI(title="LinkedIn Public Data Extractor (STRUCTURED · FREE · NO AI)")

# ------------------ MODELS ------------------

class ExtractRequest(BaseModel):
    linkedin_url: str

# ------------------ HELPERS ------------------

def extract_slug(url: str) -> Optional[str]:
    match = re.search(r"linkedin\.com/in/([^/]+)/?", url)
    return match.group(1) if match else None


def google_cse_search(slug: str, num_results: int = 5) -> List[dict]:
    query = f"site:linkedin.com/in {slug}"

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": query,
                "num": num_results
            },
            timeout=10
        )
        data = resp.json()
    except Exception as e:
        print("Google request failed:", e)
        return []

    if "error" in data:
        print("Google API error:", data["error"])
        return []

    results = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", "")
        })

    return results


def detect_profile_state(result: dict, slug: str):
    combined = f"{result['title']} {result['snippet']}".lower()

    if "profiles" in combined or "missing" in combined:
        return "private_or_restricted", 0.3

    if "/in/" not in result["url"]:
        return "ambiguous", 0.4

    if slug not in result["url"]:
        return "ambiguous", 0.4

    return "public", 0.9


# ------------------ STRUCTURING LOGIC ------------------

KNOWN_CITIES = [
    "mumbai", "pune", "nashik", "delhi", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "ahmedabad", "india"
]

def structure_google_snippet(title: str, snippet: str) -> dict:
    data = {
        "name": None,
        "headline": None,
        "about": None,
        "location": None,
        "experience": None,
        "education": None
    }

    # ---------- NAME ----------
    if "-" in title:
        data["name"] = title.split("-")[0].strip()

    # ---------- SPLIT BULLETS ----------
    parts = [p.strip() for p in re.split(r"[·|•]", snippet)]

    # ---------- ABOUT ----------
    if parts:
        data["about"] = parts[0]

    # ---------- LOCATION (ROBUST) ----------
    text_for_location = snippet.lower()
    for city in KNOWN_CITIES:
        if city in text_for_location:
            data["location"] = city.title()
            break

    # ---------- EXPERIENCE ----------
    for p in parts:
        if "experience" in p.lower():
            data["experience"] = p.split(":", 1)[-1].strip()

    # Inline experience heuristic (e.g., "Team DNote")
    if not data["experience"]:
        inline_exp = re.search(
            r"(at|with)\s+([A-Z][A-Za-z0-9 &]+)",
            snippet
        )
        if inline_exp:
            data["experience"] = inline_exp.group(2).strip()

    # ---------- EDUCATION ----------
    for p in parts:
        if "education" in p.lower():
            data["education"] = p.split(":", 1)[-1].strip()

    # ---------- HEADLINE ----------
    if data["about"]:
        headline_match = re.search(
            r"(final[- ]year.*?|computer science.*?|software engineer.*?|backend.*?|student.*?)(\.|,)",
            data["about"],
            re.IGNORECASE
        )
        if headline_match:
            data["headline"] = headline_match.group(1).strip()

    return data


# ------------------ API ------------------

@app.post("/extract")
def extract_profile(req: ExtractRequest):
    slug = extract_slug(req.linkedin_url)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid LinkedIn URL")

    results = google_cse_search(slug)

    if not results:
        return {
            "status": "not_found",
            "confidence": 0.1,
            "raw_google_data": []
        }

    first = results[0]
    status, confidence = detect_profile_state(first, slug)

    if status != "public":
        return {
            "status": status,
            "confidence": confidence,
            "raw_google_data": results
        }

    structured = structure_google_snippet(
        first["title"],
        first["snippet"]
    )

    return {
        "status": "public_structured",
        "confidence": confidence,
        "raw_google_data": first,
        "structured_data": structured
    }

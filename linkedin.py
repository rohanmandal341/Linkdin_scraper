import os
import re
import requests
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# ------------------ SETUP ------------------

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
    raise RuntimeError("Missing Google environment variables")

app = FastAPI(title="LinkedIn Public Data Extractor (Deterministic · Amazon Grade)")

# ------------------ MODELS ------------------

class ExtractRequest(BaseModel):
    linkedin_url: str

# ------------------ HELPERS ------------------

def extract_slug(url: str) -> Optional[str]:
    match = re.search(r"linkedin\.com/in/([^/]+)/?", url.lower())
    return match.group(1) if match else None


def google_cse_search(slug: str, num_results: int = 5) -> List[Dict]:
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
    except Exception:
        return []

    if "error" in data:
        return []

    return [
        {
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", "")
        }
        for item in data.get("items", [])
    ]


# ------------------ SCORING ENGINE ------------------

def score_result(result: Dict, slug: str) -> int:
    score = 0

    url = result["url"].lower()
    title = result["title"].lower()
    snippet = result["snippet"].lower()
    slug = slug.lower()

    if "linkedin.com/in/" in url:
        score += 20

    if slug in url:
        score += 40

    slug_parts = slug.replace("-", " ").split()
    if all(p in title for p in slug_parts):
        score += 20

    if "experience:" in snippet:
        score += 5
    if "education:" in snippet:
        score += 5
    if "location:" in snippet:
        score += 10

    return score


def select_best_result(results: List[Dict], slug: str) -> Optional[Dict]:
    scored = [(score_result(r, slug), r) for r in results]
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best_result = scored[0]

    if best_score < 50:
        return None

    return best_result


def has_any_slug_match(results: List[Dict], slug: str) -> bool:
    slug = slug.lower()
    return any(slug in r["url"].lower() for r in results)


# ------------------ STRUCTURING LOGIC ------------------

KNOWN_CITIES = [
    "mumbai", "pune", "delhi", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "ahmedabad",
    "india", "new york", "london"
]


def structure_google_snippet(title: str, snippet: str) -> Dict:
    data = {}

    if "-" in title:
        name = title.split("-")[0].strip()
        if name:
            data["name"] = name

    parts = [p.strip() for p in re.split(r"[·|•]", snippet)]

    if parts and parts[0] and parts[0] != "...":
        data["about"] = parts[0]

    for p in parts:
        if "experience" in p.lower():
            exp = p.split(":", 1)[-1].strip()
            if exp and exp != "...":
                data["experience"] = exp

    for p in parts:
        if "education" in p.lower():
            edu = p.split(":", 1)[-1].strip()
            if edu and edu != "...":
                data["education"] = edu

    for city in KNOWN_CITIES:
        if city in snippet.lower():
            data["location"] = city.title()
            break

    if "about" in data:
        match = re.search(
            r"(student|engineer|developer|designer|analyst|specialist|manager)[^.,]*",
            data["about"],
            re.IGNORECASE
        )
        if match:
            data["headline"] = match.group(0).strip()

    return data


# ------------------ AMAZON-STYLE RESPONSE BUILDER ------------------

def build_response(status: str, reason_code: str, reason_message: str, **extra):
    confidence_map = {
        "public_structured": 0.9,
        "ambiguous": 0.4,
        "not_found": 0.2
    }

    response = {
        "status": status,
        "confidence": confidence_map.get(status, 0.1),
        "reason_code": reason_code,
        "reason_message": reason_message
    }

    response.update(extra)
    return response


# ------------------ API ------------------

@app.post("/extract")
def extract_profile(req: ExtractRequest):
    slug = extract_slug(req.linkedin_url)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid LinkedIn URL")

    results = google_cse_search(slug)

    # CASE 1: Google returned nothing
    if not results:
        return build_response(
            status="not_found",
            reason_code="GOOGLE_NO_RESULTS",
            reason_message="Google did not return any LinkedIn profiles for this URL.",
            raw_google_data=[]
        )

    best = select_best_result(results, slug)

    # CASE 2: Results exist but NONE match the slug
    if not best and not has_any_slug_match(results, slug):
        return build_response(
            status="not_found",
            reason_code="NO_SLUG_MATCH",
            reason_message=(
                "LinkedIn profile may be private, removed, or not indexed by Google. "
                "Google returned profiles, but none match the requested LinkedIn URL."
            ),
            raw_google_data=[]
        )

    # CASE 3: Multiple weak matches
    if not best:
        return build_response(
            status="ambiguous",
            reason_code="MULTIPLE_CANDIDATES",
            reason_message=(
                "Multiple LinkedIn profiles partially match the query. "
                "Unable to determine the correct profile with high confidence."
            ),
            raw_google_data=results
        )

    # CASE 4: Public profile found
    structured = structure_google_snippet(best["title"], best["snippet"])

    return build_response(
        status="public_structured",
        reason_code="PROFILE_PUBLIC",
        reason_message="Public LinkedIn profile found and structured using Google public data.",
        raw_google_data=best,
        structured_data=structured
    )

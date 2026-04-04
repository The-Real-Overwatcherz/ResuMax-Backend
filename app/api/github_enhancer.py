"""
ResuMax Backend — GitHub Profile Enhancer API
Fetches GitHub profile data and generates AI-powered improvement suggestions.
"""

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.groq_client import get_groq_balanced, get_groq_fast, call_llm_with_fallback
from app.services.supabase import get_supabase_client

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/github", tags=["github"])

GITHUB_API_BASE = "https://api.github.com"


class GitHubAnalyzeRequest(BaseModel):
    username: str


class GitHubProfileData(BaseModel):
    username: str
    name: str | None
    bio: str | None
    company: str | None
    location: str | None
    blog: str | None
    twitter_username: str | None
    public_repos: int
    public_gists: int
    followers: int
    following: int
    created_at: str
    avatar_url: str
    html_url: str
    hireable: bool | None


class RepoData(BaseModel):
    name: str
    description: str | None
    language: str | None
    stars: int
    forks: int
    is_fork: bool
    topics: list[str]
    html_url: str
    homepage: str | None


async def fetch_github_profile(username: str) -> dict:
    """Fetch user profile from GitHub API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/users/{username}",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10.0
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"GitHub user '{username}' not found")
        if response.status_code == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded. Try again later.")
        response.raise_for_status()
        return response.json()


async def fetch_github_repos(username: str, limit: int = 30) -> list[dict]:
    """Fetch user's public repositories."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/users/{username}/repos",
            params={"sort": "updated", "per_page": limit, "type": "owner"},
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()


async def fetch_github_readme(username: str) -> str | None:
    """Fetch user's profile README (username/username repo)."""
    async with httpx.AsyncClient() as client:
        # Profile README is in a repo named same as username
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{username}/{username}/readme",
            headers={"Accept": "application/vnd.github.v3.raw"},
            timeout=10.0
        )
        if response.status_code == 200:
            return response.text
        return None


async def fetch_contribution_stats(username: str) -> dict:
    """Fetch contribution activity (events)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/users/{username}/events/public",
            params={"per_page": 100},
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10.0
        )
        if response.status_code != 200:
            return {"total_events": 0, "event_types": {}}
        
        events = response.json()
        event_types: dict[str, int] = {}
        for event in events:
            etype = event.get("type", "Unknown")
            event_types[etype] = event_types.get(etype, 0) + 1
        
        return {
            "total_events": len(events),
            "event_types": event_types
        }


def analyze_profile_data(profile: dict, repos: list[dict], readme: str | None, events: dict) -> dict:
    """Analyze the fetched data and compute metrics."""
    
    # Language distribution
    languages: dict[str, int] = {}
    total_stars = 0
    total_forks = 0
    original_repos = 0
    repos_with_description = 0
    repos_with_topics = 0
    
    for repo in repos:
        if not repo.get("fork"):
            original_repos += 1
            lang = repo.get("language")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
        
        total_stars += repo.get("stargazers_count", 0)
        total_forks += repo.get("forks_count", 0)
        
        if repo.get("description"):
            repos_with_description += 1
        if repo.get("topics"):
            repos_with_topics += 1
    
    # Sort languages by count
    sorted_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)
    
    # Calculate profile completeness score
    completeness_score = 0
    completeness_checks = {
        "has_name": bool(profile.get("name")),
        "has_bio": bool(profile.get("bio")),
        "has_location": bool(profile.get("location")),
        "has_blog": bool(profile.get("blog")),
        "has_company": bool(profile.get("company")),
        "has_twitter": bool(profile.get("twitter_username")),
        "has_readme": bool(readme),
        "has_repos": len(repos) > 0,
        "has_hireable": profile.get("hireable") is not None,
    }
    completeness_score = sum(completeness_checks.values()) / len(completeness_checks) * 100
    
    return {
        "languages": dict(sorted_languages[:10]),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "original_repos": original_repos,
        "repos_with_description": repos_with_description,
        "repos_with_topics": repos_with_topics,
        "total_repos_analyzed": len(repos),
        "completeness_score": round(completeness_score, 1),
        "completeness_checks": completeness_checks,
        "recent_activity": events,
        "has_profile_readme": bool(readme),
    }


ENHANCEMENT_PROMPT = """You are a BRUTALLY HONEST GitHub profile reviewer. You've seen thousands of developer profiles and have HIGH STANDARDS. Your job is to give tough love — be critical, direct, and demanding.

SCORING GUIDELINES (be strict!):
- 90-100: Elite profiles only (1000+ stars, perfect README, consistent activity, strong brand)
- 70-89: Good profiles with minor issues
- 50-69: Average profiles — lots of room for improvement  
- 30-49: Below average — significant problems
- 0-29: Poor — needs major overhaul

CRITICAL EVALUATION CRITERIA:
1. NO profile README = automatic -20 points (this is 2024, it's mandatory)
2. Generic/missing bio = -15 points
3. Repos without descriptions = -10 points
4. No recent activity (30+ days) = -10 points
5. Low star count with many repos = sign of low-quality projects
6. No pinned repos strategy = missed opportunity
7. Inconsistent commit patterns = looks unprofessional
8. No website/blog = missed personal branding

## PROFILE DATA:
- **Username:** {username}
- **Name:** {name}
- **Bio:** {bio}
- **Location:** {location}
- **Company:** {company}
- **Blog/Website:** {blog}
- **Twitter:** {twitter}
- **Hireable Status:** {hireable}
- **Followers:** {followers} | Following: {following}
- **Public Repos:** {public_repos}
- **Account Created:** {created_at}

## REPOSITORY ANALYSIS:
- **Total Stars:** {total_stars}
- **Total Forks:** {total_forks}
- **Original Repos (non-fork):** {original_repos}
- **Repos with descriptions:** {repos_with_description}/{total_repos}
- **Repos with topics:** {repos_with_topics}/{total_repos}
- **Top Languages:** {languages}

## TOP REPOSITORIES:
{top_repos}

## PROFILE README:
{readme_status}

## RECENT ACTIVITY (last 100 events):
{activity}

## COMPLETENESS SCORE: {completeness_score}%
Missing: {missing_fields}

---

BE CRITICAL. Don't sugarcoat. If the profile is mediocre, say so. Recruiters spend 10 seconds on a profile — would this one pass?

Provide your analysis as JSON with this exact structure:
{{
  "overall_score": <number 0-100, BE STRICT - most profiles should be 40-70>,
  "summary": "<2-3 sentence HONEST assessment - don't be nice, be helpful>",
  "strengths": ["<only list GENUINE strengths, not participation trophies>"],
  "improvements": [
    {{
      "category": "<bio|readme|repos|activity|engagement>",
      "priority": "<high|medium|low>",
      "issue": "<blunt description of what's wrong>",
      "suggestion": "<specific actionable fix>",
      "example": "<concrete example if applicable>"
    }}
  ],
  "bio_suggestion": "<improved bio text if current is weak or generic, null only if bio is already excellent>",
  "readme_sections": ["<section 1 to add>", "<section 2>", ...],
  "pinned_repo_advice": "<specific advice on which repos to pin and why>"
}}

Remember: A developer who gets honest feedback improves. A developer who gets false praise stays mediocre."""


@router.post("/analyze")
async def analyze_github_profile(
    request: GitHubAnalyzeRequest,
    user: dict = Depends(get_current_user),
):
    """
    Analyze a GitHub profile and generate AI-powered improvement suggestions.
    """
    username = request.username.strip().lstrip("@").split("/")[-1]  # Handle URLs or @mentions
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    logger.info("github_analyze_start", username=username, user_id=user["id"])
    
    # Fetch all data in parallel
    try:
        profile = await fetch_github_profile(username)
        repos = await fetch_github_repos(username)
        readme = await fetch_github_readme(username)
        events = await fetch_contribution_stats(username)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("github_fetch_failed", username=username, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch GitHub data: {str(e)}")
    
    # Analyze the data
    analysis = analyze_profile_data(profile, repos, readme, events)
    
    # Prepare top repos summary
    top_repos_list = []
    sorted_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
    for repo in sorted_repos:
        if not repo.get("fork"):
            top_repos_list.append(
                f"- **{repo['name']}**: {repo.get('description', 'No description')} "
                f"({repo.get('language', 'N/A')}, ⭐{repo.get('stargazers_count', 0)})"
            )
    
    # Missing fields
    missing = [k.replace("has_", "") for k, v in analysis["completeness_checks"].items() if not v]
    
    # Build prompt
    prompt = ENHANCEMENT_PROMPT.format(
        username=username,
        name=profile.get("name") or "Not set",
        bio=profile.get("bio") or "Not set",
        location=profile.get("location") or "Not set",
        company=profile.get("company") or "Not set",
        blog=profile.get("blog") or "Not set",
        twitter=profile.get("twitter_username") or "Not set",
        hireable="Yes" if profile.get("hireable") else "No" if profile.get("hireable") is False else "Not set",
        followers=profile.get("followers", 0),
        following=profile.get("following", 0),
        public_repos=profile.get("public_repos", 0),
        created_at=profile.get("created_at", "Unknown"),
        total_stars=analysis["total_stars"],
        total_forks=analysis["total_forks"],
        original_repos=analysis["original_repos"],
        repos_with_description=analysis["repos_with_description"],
        repos_with_topics=analysis["repos_with_topics"],
        total_repos=analysis["total_repos_analyzed"],
        languages=", ".join(f"{k} ({v})" for k, v in analysis["languages"].items()) or "None detected",
        top_repos="\n".join(top_repos_list) if top_repos_list else "No original repositories found",
        readme_status=f"Has profile README ({len(readme)} chars)" if readme else "❌ No profile README",
        activity=f"{events['total_events']} events - " + ", ".join(f"{k}: {v}" for k, v in events["event_types"].items()) if events["total_events"] > 0 else "No recent public activity",
        completeness_score=analysis["completeness_score"],
        missing_fields=", ".join(missing) if missing else "None",
    )
    
    # Get AI suggestions
    try:
        ai_response = await call_llm_with_fallback(
            primary=get_groq_balanced(),
            fallback=get_groq_fast(),
            prompt=prompt,
            system_prompt="You are a GitHub profile optimization expert. Always respond with valid JSON only.",
            parse_json=True,
        )
    except Exception as e:
        logger.error("github_ai_failed", username=username, error=str(e))
        ai_response = {
            "overall_score": analysis["completeness_score"],
            "summary": "AI analysis unavailable. See raw metrics below.",
            "strengths": [],
            "improvements": [],
            "bio_suggestion": None,
            "readme_sections": [],
            "pinned_repo_advice": None,
        }
    
    logger.info("github_analyze_complete", username=username, score=ai_response.get("overall_score"))
    
    # Build response
    response_data = {
        "username": username,
        "profile": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "avatar_url": profile.get("avatar_url"),
            "html_url": profile.get("html_url"),
            "company": profile.get("company"),
            "location": profile.get("location"),
            "blog": profile.get("blog"),
            "twitter": profile.get("twitter_username"),
            "followers": profile.get("followers"),
            "following": profile.get("following"),
            "public_repos": profile.get("public_repos"),
            "hireable": profile.get("hireable"),
            "created_at": profile.get("created_at"),
        },
        "metrics": {
            "completeness_score": analysis["completeness_score"],
            "total_stars": analysis["total_stars"],
            "total_forks": analysis["total_forks"],
            "original_repos": analysis["original_repos"],
            "languages": analysis["languages"],
            "has_profile_readme": analysis["has_profile_readme"],
            "repos_with_description": f"{analysis['repos_with_description']}/{analysis['total_repos_analyzed']}",
            "repos_with_topics": f"{analysis['repos_with_topics']}/{analysis['total_repos_analyzed']}",
            "recent_activity": analysis["recent_activity"],
        },
        "ai_analysis": ai_response,
        "top_repos": [
            {
                "name": r["name"],
                "description": r.get("description"),
                "language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "url": r.get("html_url"),
                "topics": r.get("topics", []),
            }
            for r in sorted_repos[:6] if not r.get("fork")
        ],
    }
    
    # Save report to database
    try:
        supabase = get_supabase_client()
        supabase.table("profile_reports").insert({
            "user_id": user["id"],
            "report_type": "github",
            "profile_identifier": username,
            "profile_name": profile.get("name") or username,
            "profile_image": profile.get("avatar_url"),
            "overall_score": ai_response.get("overall_score", 0),
            "report_data": response_data,
        }).execute()
        logger.info("github_report_saved", username=username, user_id=user["id"])
    except Exception as e:
        logger.warning("github_report_save_failed", error=str(e))
        # Don't fail the request if save fails
    
    return response_data


@router.get("/check/{username}")
async def check_github_user(username: str):
    """Quick check if a GitHub username exists (no auth required for this one)."""
    username = username.strip().lstrip("@").split("/")[-1]
    try:
        profile = await fetch_github_profile(username)
        return {
            "exists": True,
            "username": profile.get("login"),
            "name": profile.get("name"),
            "avatar_url": profile.get("avatar_url"),
        }
    except HTTPException as e:
        if e.status_code == 404:
            return {"exists": False, "username": username}
        raise

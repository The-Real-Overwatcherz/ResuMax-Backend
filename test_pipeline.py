"""
Quick pipeline test — bypasses auth to test the full flow.
Run: python test_pipeline.py
"""
import asyncio
import json
import sys
sys.path.insert(0, ".")

from app.services.supabase import get_supabase_client
from app.services.file_parser import parse_resume_file
from app.pipeline.graph import run_pipeline

# Sample resume text for testing
SAMPLE_RESUME = """
JOHN DOE
Software Engineer
john.doe@email.com | (555) 123-4567 | linkedin.com/in/johndoe | San Francisco, CA

SUMMARY
Experienced software engineer with 4+ years building web applications and APIs.

EXPERIENCE

Senior Software Engineer | Acme Corp | Jan 2022 - Present
• Managed the development team for multiple projects
• Built backend services using Python and Django
• Worked on database optimization tasks
• Helped with deployment and DevOps

Software Engineer | StartupXYZ | Jun 2019 - Dec 2021
• Developed features for the web application
• Fixed bugs and improved performance
• Participated in code reviews
• Responsible for testing and QA

EDUCATION
Bachelor of Science in Computer Science | Stanford University | 2015-2019 | GPA: 3.7

SKILLS
Python, JavaScript, React, Django, PostgreSQL, Git, Docker, REST APIs

CERTIFICATIONS
AWS Solutions Architect Associate
"""

SAMPLE_JD = """
Senior Backend Engineer — TechCo

We're looking for a Senior Backend Engineer to join our platform team.

Requirements:
- 5+ years of experience in backend development
- Strong proficiency in Python, Go, or Java
- Experience with Kubernetes and containerized deployments
- Deep knowledge of PostgreSQL and Redis
- Experience with microservices architecture
- Familiarity with CI/CD pipelines (GitHub Actions, Jenkins)
- Strong understanding of RESTful API design
- Experience with cloud platforms (AWS/GCP)
- Excellent communication and leadership skills

Nice to have:
- Experience with GraphQL
- Knowledge of Terraform or similar IaC tools
- Contributions to open source projects
- Experience with event-driven architectures (Kafka, RabbitMQ)

About the role:
- Build and maintain scalable backend services
- Lead technical design discussions
- Mentor junior engineers
- Collaborate cross-functionally with product and design teams
"""


async def main():
    print("=" * 60)
    print("ResuMax Pipeline Test")
    print("=" * 60)

    # Create a test analysis record
    client = get_supabase_client()

    # Use a dummy user_id
    import uuid
    
    # First, check if we have any profiles
    profiles = client.table("profiles").select("id").limit(1).execute()

    if profiles.data:
        user_id = profiles.data[0]["id"]
        print(f"\n✓ Using existing user: {user_id[:8]}...")
    else:
        # Create a test profile
        print("\n⚠ No users found. Creating test user...")
        user_id = str(uuid.uuid4())
        client.table("profiles").insert({
            "id": user_id,
            "email": "test@resumax.dev",
            "full_name": "Test User"
        }).execute()
        print(f"✓ Test user created: {user_id[:8]}...")

    # Create analysis record
    analysis = client.table("analyses").insert({
        "user_id": user_id,
        "resume_file_path": "test/resume.pdf",
        "resume_text": SAMPLE_RESUME.strip(),
        "job_description": SAMPLE_JD.strip(),
        "job_title": "Senior Backend Engineer",
        "status": "pending",
        "current_step": 0,
    }).execute()

    analysis_id = analysis.data[0]["id"]
    print(f"✓ Analysis created: {analysis_id[:8]}...")

    # Run the pipeline
    print("\n🚀 Starting pipeline...\n")

    try:
        result = await run_pipeline(
            analysis_id=analysis_id,
            resume_text=SAMPLE_RESUME.strip(),
            job_description=SAMPLE_JD.strip(),
            user_id=user_id,
            resume_file_path="test/resume.pdf",
        )

        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"\n📊 ATS Score: {result.get('ats_score', 'N/A')}")
        print(f"📈 Final Score: {result.get('final_ats_score', 'N/A')}")
        print(f"⬆️  Improvement: +{result.get('score_improvement', 0)} points")

        # Keywords
        found = result.get("total_keywords_found", 0)
        missing = result.get("total_keywords_missing", 0)
        print(f"\n🔑 Keywords: {found} found, {missing} missing")

        # Bullet rewrites
        rewrites = result.get("bullet_rewrites", [])
        print(f"\n✏️  Bullet Rewrites: {len(rewrites)}")
        for rw in rewrites[:3]:
            print(f"   BEFORE: {rw.get('original', '')[:60]}...")
            print(f"   AFTER:  {rw.get('rewritten', '')[:60]}...")
            print()

        # Suggestions
        suggestions = result.get("shruti_suggestions", [])
        print(f"💡 SHRUTI Suggestions: {len(suggestions)}")

        # Errors
        errors = result.get("errors", [])
        if errors:
            print(f"\n⚠️  Errors: {errors}")

        # Timings
        timings = result.get("node_timings", {})
        print(f"\n⏱️  Node Timings:")
        for node, ms in timings.items():
            print(f"   {node}: {ms}ms")

        total_ms = sum(timings.values())
        print(f"   TOTAL: {total_ms}ms ({total_ms/1000:.1f}s)")

        print("\n✅ Pipeline test PASSED!")

    except Exception as e:
        print(f"\n❌ Pipeline test FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

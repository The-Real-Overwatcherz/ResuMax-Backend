"""
Test your own resume directly against the pipeline!
Usage: python run_my_resume.py "path/to/your/resume.docx"
"""

import sys
import asyncio
import json
import uuid
from time import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, ".")

from app.services.file_parser import parse_resume_file
from app.pipeline.graph import run_pipeline
from app.services.supabase import get_supabase_client


async def main():
    if len(sys.argv) < 2:
        print("❌ Error: Please provide the path to your resume.")
        print('Usage: python run_my_resume.py "C:\\path\\to\\your\\resume.docx"')
        return

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"❌ Error: File not found exactly at: {filepath}")
        return

    print("=" * 60)
    print(f"📄 Loading Resume:   {filepath.name}")
    print("=" * 60)

    # Ask for a job description via input
    print("\nPaste the Job Description you want to target (Press Enter twice when done):")
    jd_lines = []
    while True:
        line = input()
        if not line and (not jd_lines or not jd_lines[-1]):
            break
        jd_lines.append(line)
        
    job_description = "\n".join(jd_lines).strip()
    
    if len(job_description) < 20:
        print("\n⚠️  Job description was too short. Using a generic Software Engineer JD for testing.")
        job_description = """
        Looking for a Software Engineer with experience in Python, web frameworks, 
        databases, cloud deployments, and building scalable backends. 
        Must be a team player with good communication skills.
        """

    # 1. Read file
    print(f"\n📂 Reading {filepath.name}...")
    file_bytes = filepath.read_bytes()
    
    try:
        resume_text = parse_resume_file(file_bytes, filepath.name)
        print(f"✓ Extracted {len(resume_text)} characters of text!")
    except Exception as e:
        print(f"❌ Failed to parse resume: {e}")
        return

    # 2. Setup DB record (bypass auth for testing)
    client = get_supabase_client()
    profiles = client.table("profiles").select("id").limit(1).execute()
    
    if profiles.data:
        user_id = profiles.data[0]["id"]
    else:
        user_id = str(uuid.uuid4())
        client.table("profiles").insert({
            "id": user_id,
            "email": "localtest@resumax.dev",
            "full_name": "Local Tester"
        }).execute()

    analysis = client.table("analyses").insert({
        "user_id": user_id,
        "resume_file_path": f"test/{filepath.name}",
        "resume_text": resume_text,
        "job_description": job_description,
        "status": "pending",
        "current_step": 0,
    }).execute()
    
    analysis_id = analysis.data[0]["id"]

    # 3. Run Pipeline
    print(f"\n🚀 Starting AI Pipeline (this will take 30-60 seconds)...\n")
    start_time = time()
    
    try:
        result = await run_pipeline(
            analysis_id=analysis_id,
            resume_text=resume_text,
            job_description=job_description,
            user_id=user_id,
            resume_file_path=f"test/{filepath.name}",
        )

        # 4. Print Results
        print("\n" + "=" * 60)
        print("🎉 PIPELINE COMPLETE!")
        print("=" * 60)
        
        print(f"\n📊 Original ATS Score: {result.get('ats_score', 0)}")
        print(f"📈 Optimized ATS Score: {result.get('final_ats_score', 0)}")
        print(f"⬆️  Improvement: +{result.get('score_improvement', 0)} points")

        # Bullet rewrites
        rewrites = result.get("bullet_rewrites", [])
        if rewrites:
            print(f"\n✏️  Top 3 Bullet Rewrites:")
            for rw in rewrites[:3]:
                print(f"   BEFORE: {rw.get('original', '')[:70]}...")
                print(f"   AFTER:  {rw.get('rewritten', '')[:70]}...\n")

        # Save full dump
        dump_file = filepath.parent / f"resumax_results_{filepath.stem}.json"
        with open(dump_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
            
        print(f"\n💾 Full massive JSON results saved to:")
        print(f"   {dump_file.absolute()}")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

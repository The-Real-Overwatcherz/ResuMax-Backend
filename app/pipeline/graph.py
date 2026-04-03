"""
ResuMax — LangGraph Pipeline Graph
Wires all 8 nodes into a sequential StateGraph with error handling,
Supabase status updates, and Realtime progress broadcasting.
"""

import asyncio
import structlog
from time import time

from langgraph.graph import StateGraph, END

from app.pipeline.state import PipelineState
from app.pipeline.nodes.parser import parse_resume_node
from app.pipeline.nodes.ats_scorer import ats_scoring_node
from app.pipeline.nodes.deep_analyzer import deep_analysis_node
from app.pipeline.nodes.skill_matcher import skill_matching_node
from app.pipeline.nodes.interviewer import interviewer_node
from app.pipeline.nodes.bullet_rewriter import bullet_rewriter_node
from app.pipeline.nodes.density_checker import density_checker_node
from app.pipeline.nodes.optimizer import final_optimizer_node

from app.services.supabase import update_analysis_status, broadcast_progress

logger = structlog.get_logger(__name__)

# ── Progress Messages ────────────────────────────────────────────

STEP_CONFIG = {
    "parse_resume":       {"step": 1, "status": "parsing",      "message": "Extracting resume data...",        "percentage": 15},
    "ats_score":          {"step": 2, "status": "scoring",       "message": "Calculating ATS score...",         "percentage": 30},
    "deep_analyze":       {"step": 3, "status": "analyzing",     "message": "Running deep analysis...",         "percentage": 45},
    "match_skills":       {"step": 3, "status": "analyzing",     "message": "Matching skills semantically...",  "percentage": 55},
    "generate_interview": {"step": 4, "status": "interviewing",  "message": "Generating interview questions...", "percentage": 65},
    "rewrite_bullets":    {"step": 5, "status": "rewriting",     "message": "Rewriting bullet points...",       "percentage": 80},
    "check_density":      {"step": 5, "status": "rewriting",     "message": "Checking keyword density...",     "percentage": 90},
    "optimize_final":     {"step": 6, "status": "optimizing",    "message": "Running final optimization...",  "percentage": 95},
}


# ── Safe Node Wrapper ────────────────────────────────────────────

def make_safe_node(node_fn, node_name: str):
    """Wrap a node function with error handling and progress broadcasting."""

    async def safe_wrapper(state: PipelineState) -> dict:
        config = STEP_CONFIG.get(node_name, {})
        analysis_id = state.get("analysis_id", "")

        # Broadcast progress to frontend
        try:
            await broadcast_progress(
                analysis_id=analysis_id,
                step=config.get("step", 0),
                status=config.get("status", "processing"),
                message=config.get("message", f"Processing {node_name}..."),
                percentage=config.get("percentage", 0),
            )
        except Exception:
            pass  # Don't fail pipeline if broadcast fails

        # Update Supabase status
        try:
            await update_analysis_status(
                analysis_id=analysis_id,
                status=config.get("status", "processing"),
                step=config.get("step", 0),
            )
        except Exception:
            pass  # Don't fail pipeline if DB update fails

        # Throttle: wait before calling LLM to avoid Groq rate limits
        if node_name != "parse_resume":
            await asyncio.sleep(8)

        # Run the actual node
        try:
            result = await node_fn(state)
            logger.info(f"node_{node_name}_success", analysis_id=analysis_id)
            return result
        except Exception as e:
            logger.error(f"node_{node_name}_failed", error=str(e), analysis_id=analysis_id)
            errors = state.get("errors", [])
            errors.append(f"{node_name}: {str(e)}")
            return {"errors": errors}

    return safe_wrapper


# ── Build Graph ──────────────────────────────────────────────────

def build_pipeline() -> StateGraph:
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(PipelineState)

    # Add nodes with safe wrappers
    graph.add_node("parse_resume",       make_safe_node(parse_resume_node, "parse_resume"))
    graph.add_node("ats_score",          make_safe_node(ats_scoring_node, "ats_score"))
    graph.add_node("deep_analyze",       make_safe_node(deep_analysis_node, "deep_analyze"))
    graph.add_node("match_skills",       make_safe_node(skill_matching_node, "match_skills"))
    graph.add_node("generate_interview", make_safe_node(interviewer_node, "generate_interview"))
    graph.add_node("rewrite_bullets",    make_safe_node(bullet_rewriter_node, "rewrite_bullets"))
    graph.add_node("check_density",      make_safe_node(density_checker_node, "check_density"))
    graph.add_node("optimize_final",     make_safe_node(final_optimizer_node, "optimize_final"))

    # Define edges (linear flow)
    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", "ats_score")
    graph.add_edge("ats_score", "deep_analyze")
    graph.add_edge("deep_analyze", "match_skills")
    graph.add_edge("match_skills", "generate_interview")
    graph.add_edge("generate_interview", "rewrite_bullets")
    graph.add_edge("rewrite_bullets", "check_density")
    graph.add_edge("check_density", "optimize_final")
    graph.add_edge("optimize_final", END)

    return graph


# Compile once at module level
pipeline_graph = build_pipeline()
compiled_pipeline = pipeline_graph.compile()


# ── Run Pipeline ─────────────────────────────────────────────────

async def run_pipeline(
    analysis_id: str,
    resume_text: str,
    job_description: str,
    user_id: str,
    resume_file_path: str = "",
) -> dict:
    """
    Execute the full 8-node pipeline.
    Called as a background task from the API endpoint.
    Returns the final pipeline state.
    """
    logger.info("pipeline_start", analysis_id=analysis_id, user_id=user_id)
    start_time = time()

    # Initialize state
    initial_state: PipelineState = {
        "resume_text": resume_text,
        "resume_file_path": resume_file_path,
        "job_description": job_description,
        "job_title": None,
        "user_id": user_id,
        "analysis_id": analysis_id,
        "parsed_resume": None,
        "ats_score": None,
        "ats_breakdown": None,
        "keyword_matches": None,
        "total_keywords_found": None,
        "total_keywords_missing": None,
        "deep_analysis": None,
        "skill_analysis": None,
        "interview_questions": None,
        "bullet_rewrites": None,
        "total_bullets_rewritten": None,
        "density_analysis": None,
        "optimized_resume": None,
        "final_ats_score": None,
        "score_improvement": None,
        "shruti_suggestions": None,
        "current_step": 0,
        "status": "pending",
        "errors": [],
        "processing_start_time": start_time,
        "node_timings": {},
    }

    try:
        # Run the compiled pipeline
        final_state = await compiled_pipeline.ainvoke(initial_state)

        total_ms = int((time() - start_time) * 1000)

        # Save final results to Supabase
        await update_analysis_status(
            analysis_id=analysis_id,
            status="completed",
            step=6,
            job_title=final_state.get("job_title"),
            parsed_resume=final_state.get("parsed_resume"),
            ats_score=final_state.get("ats_score"),
            ats_breakdown=final_state.get("ats_breakdown"),
            keyword_analysis={
                "total_found": final_state.get("total_keywords_found", 0),
                "total_missing": final_state.get("total_keywords_missing", 0),
                "matches": final_state.get("keyword_matches", []),
            },
            skill_analysis=final_state.get("skill_analysis"),
            deep_analysis=final_state.get("deep_analysis"),
            star_rewrites=final_state.get("bullet_rewrites"),
            density_analysis=final_state.get("density_analysis"),
            optimized_resume=final_state.get("optimized_resume"),
            shruti_suggestions=final_state.get("shruti_suggestions"),
            shruti_conversation=[],
            processing_time_ms=total_ms,
        )

        # Broadcast completion
        await broadcast_progress(
            analysis_id=analysis_id,
            step=6, status="completed",
            message="Optimization complete!",
            percentage=100,
        )

        logger.info(
            "pipeline_complete",
            analysis_id=analysis_id,
            total_ms=total_ms,
            ats_score=final_state.get("ats_score"),
            final_score=final_state.get("final_ats_score"),
            errors=final_state.get("errors", []),
        )

        return final_state

    except Exception as e:
        logger.error("pipeline_failed", analysis_id=analysis_id, error=str(e))

        # Mark as failed in Supabase
        await update_analysis_status(
            analysis_id=analysis_id,
            status="failed",
            step=initial_state.get("current_step", 0),
        )

        # Broadcast failure
        try:
            await broadcast_progress(
                analysis_id=analysis_id,
                step=0, status="failed",
                message=f"Pipeline failed: {str(e)}",
                percentage=0,
            )
        except Exception:
            pass

        raise

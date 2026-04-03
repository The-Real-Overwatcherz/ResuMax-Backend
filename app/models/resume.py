"""
ResuMax — Resume Pydantic Models
Structured data models for parsed resume content.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class ResumeContact(BaseModel):
    """Contact information extracted from resume header."""
    full_name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    location: Optional[str] = None


class ExperienceEntry(BaseModel):
    """Single work experience entry."""
    company: str
    title: str
    dates: str = ""                        # e.g. "Jan 2022 - Present"
    bullets: List[str] = Field(default_factory=list)
    is_current: bool = False


class EducationEntry(BaseModel):
    """Single education entry."""
    institution: str
    degree: str
    field: Optional[str] = None
    dates: Optional[str] = None
    gpa: Optional[str] = None


class ParsedResume(BaseModel):
    """
    Complete structured resume — output of the parser node.
    Contains all sections extracted from raw resume text.
    """
    contact: ResumeContact = Field(default_factory=ResumeContact)
    summary: Optional[str] = None
    experience: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    projects: List[dict] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    raw_text: str = ""

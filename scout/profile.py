import json
import os
from typing import List
from pydantic import BaseModel

PROFILE_FILE = "scout_profile.json"

class UserProfile(BaseModel):
    name: str = ""
    firstName: str = ""
    senderEmail: str = ""
    title: str = ""
    institution: str = ""
    graduatingYear: str = ""
    mobileNumber: str = ""
    credentials: List[str] = []
    github: str = ""
    linkedin: str = ""
    smtpHost: str = "smtp.gmail.com"
    smtpPort: int = 587
    smtpPassword: str = ""

def load_profile() -> UserProfile:
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE) as f:
                data = json.load(f)
            return UserProfile(**data)
        except Exception:
            pass
    return UserProfile()

def save_profile(profile: UserProfile):
    with open(PROFILE_FILE, "w") as f:
        json.dump(profile.model_dump(), f, indent=2)

def build_persona_prompt(profile: UserProfile) -> str:
    """Convert a UserProfile into the LLM system prompt persona block."""
    if not profile.name:
        return ""

    first_name = (profile.firstName or profile.name.split()[0])

    lines = []
    lines.append(f"Candidate Name: {profile.name}")
    if profile.title:
        lines.append(f"Role/Title: {profile.title}")
    if profile.institution:
        lines.append(f"Institution/Current Company: {profile.institution}")
    if profile.graduatingYear:
        lines.append(f"Graduating Year: {profile.graduatingYear}")

    if profile.credentials:
        lines.append("\nKey Credentials & Achievements:")
        for cred in profile.credentials:
            if cred.strip():
                lines.append(f"  - {cred.strip()}")

    contact_parts = []
    if profile.senderEmail:
        contact_parts.append(f"Email: {profile.senderEmail}")
    if profile.mobileNumber:
        contact_parts.append(f"Phone: {profile.mobileNumber}")
    if profile.github:
        contact_parts.append(f"GitHub: {profile.github}")
    if profile.linkedin:
        contact_parts.append(f"LinkedIn: {profile.linkedin}")

    if contact_parts:
        lines.append("\nContact Details:")
        for cp in contact_parts:
            lines.append(f"  {cp}")

    return "\n".join(lines)

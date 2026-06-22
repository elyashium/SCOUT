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

    first_name = (profile.firstName or profile.name.split()[0]).lower()

    intro = f"you are writing a cold outreach email on behalf of {profile.name.lower()}"
    if profile.title:
        intro += f", a {profile.title.lower()}"
    if profile.institution:
        intro += f" at {profile.institution.lower()}"
    if profile.graduatingYear:
        intro += f", graduating {profile.graduatingYear}"
    intro += "."

    lines = [intro, "", f"{first_name}'s credentials:"]
    for cred in profile.credentials:
        if cred.strip():
            lines.append(f"- {cred.strip()}")

    link_parts = []
    if profile.github:
        link_parts.append(f"github: {profile.github}")
    if profile.linkedin:
        link_parts.append(f"linkedin: {profile.linkedin}")
    if link_parts:
        lines.append(f"- {' | '.join(link_parts)}")

    return "\n".join(lines)

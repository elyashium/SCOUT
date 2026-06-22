import json
import os
from typing import List, Dict

COMPANIES_FILE = "scout_companies.json"

DEFAULT_COMPANIES = [
    {"name": "Floe", "domain": "floe.xyz", "industry": "fintech infrastructure", "description": "spend management for AI agents", "recipientEmail": ""},
    {"name": "Alchemyst AI", "domain": "getalchemystai.com", "industry": "AI infrastructure", "description": "context engine for AI agents", "recipientEmail": ""},
    {"name": "NeoFi", "domain": "neofi.co", "industry": "crypto fintech", "description": "crypto exchange platform", "recipientEmail": ""},
    {"name": "GTMer", "domain": "gtmer.ai", "industry": "sales AI", "description": "AI-powered outbound sales agents", "recipientEmail": ""},
    {"name": "ENGINPILOT", "domain": "enginpilot.com", "industry": "industrial AI", "description": "engineering intelligence OS", "recipientEmail": ""},
    {"name": "Ceryneian", "domain": "ceryneianpartners.com", "industry": "fintech", "description": "algorithmic trading platform", "recipientEmail": ""},
]

def load_companies() -> List[Dict]:
    if os.path.exists(COMPANIES_FILE):
        try:
            with open(COMPANIES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return [c.copy() for c in DEFAULT_COMPANIES]

def save_companies(companies: List[Dict]):
    with open(COMPANIES_FILE, "w") as f:
        json.dump(companies, f, indent=2)

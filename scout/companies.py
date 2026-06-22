import json
import os
from typing import List, Dict

COMPANIES_FILE = "scout_companies.json"

DEFAULT_COMPANIES = [
    {"name": "Floe", "recipientEmail": ""},
    {"name": "Alchemyst AI", "recipientEmail": ""},
    {"name": "NeoFi", "recipientEmail": ""},
    {"name": "GTMer", "recipientEmail": ""},
    {"name": "ENGINPILOT", "recipientEmail": ""},
    {"name": "Ceryneian", "recipientEmail": ""},
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

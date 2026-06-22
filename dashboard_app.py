import streamlit as st
import json
import os
import subprocess
import sys
import pandas as pd
import time
import threading
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

from scout.profile import UserProfile, load_profile, save_profile, build_persona_prompt
from scout.companies import load_companies, save_companies
from scout.email_sender import send_cold_email

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SCOUT Terminal",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Premium Terminal CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
/* Premium Greyish Dark Matrix Theme */
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;500;600&display=swap');

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
    background-color: #121416 !important;
    color: #16a34a !important;
    font-family: 'Fira Code', 'Consolas', monospace !important;
    font-size: 13px !important;
}

#MainMenu, footer, header { visibility: hidden; }

/* Navbar Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 16px;
    background-color: #1a1c1f;
    padding: 10px 20px;
    border-radius: 4px;
    border: 1px solid rgba(22, 163, 74, 0.2);
}
.stTabs [data-baseweb="tab"] {
    padding: 8px 16px;
    color: #6b8273 !important;
    border: none;
    font-weight: 500;
    font-family: 'Fira Code', 'Consolas', monospace !important;
    letter-spacing: 1px;
}
.stTabs [aria-selected="true"] {
    background-color: rgba(22, 163, 74, 0.1) !important;
    color: #16a34a !important;
    border-bottom: 2px solid #16a34a !important;
}

h1, h2, h3, h4, h5, h6, p, label, li {
    font-family: 'Fira Code', 'Consolas', monospace !important;
}

h1, h2, h3 {
    color: #16a34a !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    border-bottom: 1px solid rgba(22, 163, 74, 0.2) !important;
    padding-bottom: 8px;
    letter-spacing: 1px;
}

.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
    color: #6b8273 !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Specific targeting to avoid breaking stSelectbox SVG inner elements */
input[type="text"], input[type="number"], input[type="password"], textarea, [data-baseweb="select"] {
    background-color: #1a1c1f !important;
    border: 1px solid rgba(22, 163, 74, 0.3) !important;
    border-radius: 4px !important;
    color: #16a34a !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
    transition: all 0.2s ease !important;
}

input:focus, textarea:focus {
    border-color: #16a34a !important;
    box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.1) !important;
}

.stButton > button {
    background-color: #1a1c1f !important;
    color: #16a34a !important;
    border: 1px solid rgba(22, 163, 74, 0.4) !important;
    border-radius: 4px !important;
    font-weight: 500 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background-color: rgba(22, 163, 74, 0.1) !important;
    border-color: #16a34a !important;
    color: #15b850 !important;
}
.stButton > button[kind="primary"] {
    background-color: #16a34a !important;
    color: #121416 !important;
    border: 1px solid #16a34a !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #15b850 !important;
    box-shadow: 0 4px 12px rgba(22, 163, 74, 0.2) !important;
}

.streamlit-expanderHeader {
    background-color: #1a1c1f !important;
    border: 1px solid rgba(22, 163, 74, 0.2) !important;
    border-radius: 4px !important;
    color: #16a34a !important;
    font-size: 13px !important;
    transition: background-color 0.2s ease;
}
.streamlit-expanderHeader:hover {
    background-color: rgba(22, 163, 74, 0.05) !important;
}
.streamlit-expanderContent {
    background-color: #15171a !important;
    border: 1px solid rgba(22, 163, 74, 0.2) !important;
    border-top: none !important;
    border-radius: 0 0 4px 4px !important;
    padding: 16px !important;
}

[data-testid="stTable"], .stDataFrame { 
    background-color: #1a1c1f !important;
    border: 1px solid rgba(22, 163, 74, 0.2) !important;
    border-radius: 4px !important;
    font-size: 12px !important;
}

hr { border-color: rgba(22, 163, 74, 0.2) !important; margin: 24px 0 !important; }

.stSuccess { background: rgba(22, 163, 74, 0.05) !important; border: 1px solid rgba(22, 163, 74, 0.3) !important; border-radius: 4px !important; color: #16a34a !important; font-size: 12px !important; }
.stError   { background: rgba(239, 68, 68, 0.05) !important; border: 1px solid rgba(239, 68, 68, 0.3) !important; border-radius: 4px !important; color: #ef4444 !important; font-size: 12px !important; }
.stWarning { background: rgba(245, 158, 11, 0.05) !important; border: 1px solid rgba(245, 158, 11, 0.3) !important; border-radius: 4px !important; color: #f59e0b !important; font-size: 12px !important; }
.stInfo    { background: rgba(59, 130, 246, 0.05) !important; border: 1px solid rgba(59, 130, 246, 0.3) !important; border-radius: 4px !important; color: #3b82f6 !important; font-size: 12px !important; }

pre, code {
    background-color: #15171a !important;
    border: 1px solid rgba(22, 163, 74, 0.2) !important;
    border-radius: 4px !important;
    color: #16a34a !important;
    font-family: 'Fira Code', 'Consolas', monospace !important;
    font-size: 12px !important;
}

[data-testid="stVerticalBlock"] > div {
    padding-bottom: 4px !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────
def metric_card(label, value, sublabel=None):
    sub = f"<p style='color:#6b8273;font-size:10px;margin:4px 0 0;font-weight:400;'>{sublabel}</p>" if sublabel else ""
    st.markdown(f"""
    <div style='background:#1a1c1f;border:1px solid rgba(22, 163, 74, 0.2);
                border-radius:4px;padding:16px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.2);'>
        <p style='color:#16a34a;font-size:24px;font-weight:600;margin:0;line-height:1'>{value}</p>
        <p style='color:#6b8273;font-size:10px;margin:6px 0 0;text-transform:uppercase;letter-spacing:1px;font-weight:500;'>{label}</p>
        {sub}
    </div>""", unsafe_allow_html=True)

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def extract_profile_from_resume(text: str) -> dict:
    if not LANGCHAIN_AVAILABLE:
        return {}
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            st.error("GROQ_API_KEY not found in environment.")
            return {}
        llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0, api_key=api_key)
        prompt = f"""
        Extract the following information from the resume text into a JSON object.
        Keys required:
        - "name": full name
        - "title": current or target job title
        - "institution": current company or university
        - "graduatingYear": year of graduation if applicable
        - "github": github url
        - "linkedin": linkedin url
        - "credentials": list of top 3-5 impressive projects, achievements, or roles (max 15 words each)

        Return ONLY valid JSON.
        Resume:
        {text[:5000]}
        """
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
        return json.loads(content)
    except Exception as e:
        st.error(f"Failed to parse resume with AI: {e}")
        return {}


# ─── Header ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:left; padding: 10px 0 10px 0; border-bottom: 1px solid rgba(22, 163, 74, 0.2); margin-bottom: 16px;'>
    <p style='font-size:24px; font-weight:600; margin:0; letter-spacing:2px; color:#16a34a;'>SCOUT <span style='color:#6b8273; font-weight:400;'>// SYSTEM CONTROL</span></p>
    <p style='font-size:11px; margin:4px 0 0; letter-spacing:1px; color:#6b8273; text-transform: uppercase;'>Spend-Conscious Outreach & Understanding Tool</p>
</div>
""", unsafe_allow_html=True)

# ─── Navbar Tabs ─────────────────────────────────────────────────────────────────
tab_profile, tab_targets, tab_pipeline, tab_transmission = st.tabs([
    "01 PROFILE", "02 TARGETS", "03 PIPELINE", "04 TRANSMISSION"
])

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 1: PROFILE
# ══════════════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.markdown("### 01. PROFILE & IDENTITY")
    
    if PDF_AVAILABLE and LANGCHAIN_AVAILABLE:
        with st.expander("RESUME AI AUTOFILL", expanded=True):
            pdf_file = st.file_uploader("Upload PDF Resume for Auto-fill", type=["pdf"])
            if pdf_file:
                if st.button("PARSE RESUME WITH AI"):
                    with st.spinner("Analyzing resume..."):
                        reader = PdfReader(pdf_file)
                        text = "\\n".join(page.extract_text() or "" for page in reader.pages)
                        extracted = extract_profile_from_resume(text)
                        
                        if extracted:
                            current_profile = load_profile()
                            current_profile.name = extracted.get("name", current_profile.name)
                            current_profile.title = extracted.get("title", current_profile.title)
                            current_profile.institution = extracted.get("institution", current_profile.institution)
                            current_profile.graduatingYear = extracted.get("graduatingYear", current_profile.graduatingYear)
                            current_profile.github = extracted.get("github", current_profile.github)
                            current_profile.linkedin = extracted.get("linkedin", current_profile.linkedin)
                            current_profile.credentials = extracted.get("credentials", current_profile.credentials)
                            save_profile(current_profile)
                            st.success("PROFILE AUTO-FILLED SUCCESSFULLY!")
                            st.rerun()
    
    profile = load_profile()
    
    with st.expander("SENDER PROFILE", expanded=True):
        name         = st.text_input("Full Name",          value=profile.name)
        sender_email = st.text_input("Your Email",         value=profile.senderEmail)
        title        = st.text_input("Target Job Title",   value=profile.title)
        institution  = st.text_input("Institution / Company", value=profile.institution)
        grad_year    = st.text_input("Graduating / Since", value=profile.graduatingYear)

        github   = st.text_input("GitHub",   value=profile.github)
        linkedin = st.text_input("LinkedIn", value=profile.linkedin)

        creds_default = "\\n".join(profile.credentials) if profile.credentials else ""
        creds_text = st.text_area(
            "Credentials (one per line)",
            value=creds_default,
            height=150
        )

        st.markdown("**OPTIONAL: SMTP SETTINGS (For auto-sending)**")
        smtp_host = st.text_input("SMTP Host",     value=profile.smtpHost)
        smtp_port = st.number_input("SMTP Port",   value=profile.smtpPort, min_value=1, max_value=65535, step=1)
        smtp_pass = st.text_input("SMTP Password / App Password", value=profile.smtpPassword, type="password")

        if st.button("SAVE PROFILE", type="primary", use_container_width=True):
            new_profile = UserProfile(
                name=name,
                firstName=name.split()[0] if name else "",
                senderEmail=sender_email,
                title=title,
                institution=institution,
                graduatingYear=grad_year,
                credentials=[c.strip() for c in creds_text.splitlines() if c.strip()],
                github=github,
                linkedin=linkedin,
                smtpHost=smtp_host,
                smtpPort=int(smtp_port),
                smtpPassword=smtp_pass,
            )
            save_profile(new_profile)
            st.success("PROFILE SAVED SUCCESSFULLY.")
    
    with st.expander("LIVE PERSONA PREVIEW"):
        preview_profile = UserProfile(
            name=name if 'name' in locals() else profile.name,
            firstName=(name.split()[0] if name else profile.firstName) if 'name' in locals() else profile.firstName,
            title=title if 'title' in locals() else profile.title,
            institution=institution if 'institution' in locals() else profile.institution,
            graduatingYear=grad_year if 'grad_year' in locals() else profile.graduatingYear,
            credentials=[c.strip() for c in (creds_text.splitlines() if 'creds_text' in locals() else profile.credentials) if c.strip()],
            github=github if 'github' in locals() else profile.github,
            linkedin=linkedin if 'linkedin' in locals() else profile.linkedin,
        )
        persona_preview = build_persona_prompt(preview_profile)
        st.code(persona_preview or "NO DATA", language="text")

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 2: TARGET COMPANIES
# ══════════════════════════════════════════════════════════════════════════════════
with tab_targets:
    st.markdown("### 02. TARGET COMPANIES")
    companies = load_companies()
    if "companies" not in st.session_state:
        st.session_state.companies = companies
    companies = st.session_state.companies

    st.info("The agent will automatically scrape the web for job openings relevant to your profile.")

    with st.expander("ADD NEW TARGET"):
        new_name    = st.text_input("Company Name", key="new_name")
        new_email   = st.text_input("Recipient Email (Optional)", key="new_email")

        if st.button("ADD TARGET", type="primary"):
            if new_name:
                companies.append({
                    "name": new_name,
                    "recipientEmail": new_email
                })
                st.session_state.companies = companies
                save_companies(companies)
                st.rerun()

    for i, company in enumerate(companies):
        with st.expander(f"TARGET: {company['name'].upper()}"):
            e1, e2 = st.columns(2)
            companies[i]["name"]           = e1.text_input("Name",    value=company["name"],           key=f"name_{i}")
            companies[i]["recipientEmail"] = e2.text_input("Recipient Email", value=company.get("recipientEmail",""), key=f"email_{i}")

            if st.button("REMOVE TARGET", key=f"remove_{i}"):
                companies.pop(i)
                st.session_state.companies = companies
                save_companies(companies)
                st.rerun()

    if st.button("SAVE TARGET LIST", key="save_companies"):
        st.session_state.companies = companies
        save_companies(companies)
        st.success("TARGET LIST SAVED.")

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 3: PIPELINE EXECUTION
# ══════════════════════════════════════════════════════════════════════════════════
with tab_pipeline:
    st.markdown("### 03. PIPELINE EXECUTION & METRICS")
    
    col_exec, col_metrics = st.columns([1, 2], gap="large")
    
    with col_exec:
        st.markdown("#### LAUNCH SEQUENCE")
        global_budget = st.number_input("Global Budget (USD)", value=0.10, min_value=0.01, step=0.01, format="%.3f")
        per_cap       = st.number_input("Per-Company Cap (USD)", value=0.012, min_value=0.001, step=0.001, format="%.3f")
        
        if st.button("EXECUTE SCOUT PIPELINE", type="primary", use_container_width=True):
            save_companies(st.session_state.companies)
            with st.spinner("INITIATING PIPELINE SEQUENCE..."):
                py_cmd = "py" if os.name == "nt" else "python3"
                result = subprocess.run(
                    [py_cmd, "main.py",
                     "--global-budget", str(global_budget),
                     "--per-cap", str(per_cap)],
                    capture_output=True, text=True, cwd=os.getcwd()
                )
            if result.returncode == 0:
                st.success("PIPELINE EXECUTION COMPLETE.")
                st.rerun()
            else:
                st.error("PIPELINE ENCOUNTERED AN ERROR.")
                st.code(result.stderr[-3000:] if result.stderr else "NO ERROR OUTPUT", language="bash")

    with col_metrics:
        st.markdown("#### LEDGER & METRICS")
        if st.button("REFRESH DATA LOGS", key="refresh_results"):
            st.rerun()

        ledger = load_json("scout_ledger.json")
        meta   = load_json("scout_meta_analysis.json")

        if not ledger:
            st.info("NO DATA AVAILABLE. EXECUTE PIPELINE TO GENERATE LOGS.")
        else:
            total_spent = sum(c.get("totalCostUSD", 0) for c in ledger.values())
            emails_gen  = len([c for c in ledger.values() if c.get("email")])
            exceeded    = sum(1 for c in ledger.values() if c.get("budgetStatus") == "exceeded")

            m1, m2, m3, m4 = st.columns(4)
            with m1: metric_card("TOTAL SPENT", f"${total_spent:.4f}")
            with m2: metric_card("COMPANIES", str(len(ledger)))
            with m3: metric_card("EMAILS GEN", str(emails_gen))
            with m4: metric_card("EXCEEDED", str(exceeded))

            with st.expander("RAW LEDGER DATAFRAME"):
                rows = []
                for company, d in ledger.items():
                    rows.append({
                        "COMPANY":         company,
                        "SPENT":           f"${d.get('totalCostUSD',0):.4f}",
                        "DECISION":        str(d.get("decision","--")).upper(),
                        "STATUS":          str(d.get("budgetStatus","--")).upper(),
                        "EMAIL":           "YES" if d.get("email") else "NO",
                        "TOP SIGNAL":      (d.get("signals") or ["--"])[0][:30],
                    })
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════════
# TAB 4: TRANSMISSION
# ══════════════════════════════════════════════════════════════════════════════════
with tab_transmission:
    st.markdown("### 04. TRANSMISSION TERMINAL")
    emails = load_json("scout_emails.json")
    
    if not emails:
        st.info("NO EMAILS PENDING TRANSMISSION.")
    else:
        subject_template = st.text_input(
            "Subject Template",
            value="Application for Role — {company}",
        )
        
        if "send_status" not in st.session_state:
            st.session_state.send_status = {}

        select_all = st.checkbox("Select all companies", value=False, key="select_all")
        companies_list = load_companies()
        recipient_map  = {c["name"]: c.get("recipientEmail", "") for c in companies_list}

        for company, email_text in emails.items():
            sent_before = st.session_state.send_status.get(company)
            status_tag = " :: SENT" if sent_before is True else (" :: FAILED" if sent_before is False else "")

            with st.expander(f"PAYLOAD: {company.upper()}{status_tag}"):
                recipient = st.text_input(
                    "Recipient Email",
                    value=recipient_map.get(company, ""),
                    key=f"recip_{company}"
                )
                final_subject = subject_template.replace("{company}", company)
                st.markdown(f"**SUBJECT:** `{final_subject}`")
                edited_email = st.text_area(
                    "BODY",
                    value=email_text,
                    height=200,
                    key=f"body_{company}"
                )

                has_smtp = bool(profile.senderEmail and profile.smtpPassword)
                
                if not has_smtp:
                    st.info("SMTP Credentials missing. Copy the email above and send it manually via your email client.")
                    st.code(f"To: {recipient}\\nSubject: {final_subject}\\n\\n{edited_email}", language="text")
                else:
                    send_this = st.checkbox("Include in batch transmission", value=select_all, key=f"sel_{company}")

                    if st.button(f"TRANSMIT TO {company.upper()}", key=f"send_{company}"):
                        if not recipient:
                            st.warning("RECIPIENT EMAIL REQUIRED.")
                        else:
                            with st.spinner(f"TRANSMITTING TO {recipient}..."):
                                ok, msg = send_cold_email(
                                    smtp_host=profile.smtpHost,
                                    smtp_port=int(profile.smtpPort),
                                    sender_email=profile.senderEmail,
                                    sender_password=profile.smtpPassword,
                                    recipient_email=recipient,
                                    subject=final_subject,
                                    body=edited_email
                                )
                            st.session_state.send_status[company] = ok
                            if ok:
                                st.success(f"TRANSMISSION SUCCESSFUL: {msg}")
                            else:
                                st.error(f"TRANSMISSION FAILED: {msg}")

        has_smtp = bool(profile.senderEmail and profile.smtpPassword)
        if has_smtp:
            if st.button("BATCH TRANSMIT SELECTED", type="primary", use_container_width=True):
                selected = [c for c in emails if st.session_state.get(f"sel_{c}", False)]
                if not selected:
                    st.warning("NO TARGETS SELECTED FOR BATCH TRANSMISSION.")
                else:
                    prog = st.progress(0, text="TRANSMITTING PAYLOADS...")
                    for i, company in enumerate(selected):
                        recipient = st.session_state.get(f"recip_{company}", recipient_map.get(company, ""))
                        body      = st.session_state.get(f"body_{company}", emails[company])
                        subj      = subject_template.replace("{company}", company)
                        if recipient:
                            ok, msg = send_cold_email(
                                profile.smtpHost, int(profile.smtpPort), 
                                profile.senderEmail, profile.smtpPassword, 
                                recipient, subj, body
                            )
                            st.session_state.send_status[company] = ok
                            st.markdown(f"{'SUCCESS' if ok else 'FAILED'} : {company} -> {recipient}")
                        else:
                            st.markdown(f"SKIPPED : {company} - NO RECIPIENT")
                        prog.progress((i + 1) / len(selected), text=f"SENT {i+1}/{len(selected)}")
                    prog.empty()
                    st.success(f"BATCH TRANSMISSION COMPLETE ({len(selected)} TARGETS)")

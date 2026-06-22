import streamlit as st
import json
import os
import subprocess
import sys
import pandas as pd
import time
import threading

from scout.profile import UserProfile, load_profile, save_profile, build_persona_prompt
from scout.companies import load_companies, save_companies
from scout.email_sender import send_cold_email

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SCOUT Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Premium CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
    background: #080b14 !important;
    color: #e2e8f0 !important;
}

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 6px;
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 24px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 22px;
    font-size: 0.875rem;
    font-weight: 500;
    color: #94a3b8;
    background: transparent;
    border: none;
    transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(6,182,212,0.2), rgba(139,92,246,0.2)) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(6,182,212,0.3) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stNumberInput > div > div > input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(6,182,212,0.5) !important;
    box-shadow: 0 0 0 3px rgba(6,182,212,0.08) !important;
}

/* Buttons */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #06b6d4, #8b5cf6) !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 25px rgba(6,182,212,0.3) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.06) !important;
    color: #94a3b8 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-weight: 500 !important;
}
.streamlit-expanderContent {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
}

/* Dataframe */
.stDataFrame { border-radius: 10px; overflow: hidden; }

/* Labels */
.stTextInput label, .stTextArea label, .stNumberInput label,
.stSelectbox label, .stSlider label, .stFileUploader label {
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* Dividers */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* Alerts */
.stSuccess { background: rgba(16,185,129,0.1) !important; border: 1px solid rgba(16,185,129,0.25) !important; border-radius: 10px !important; }
.stError   { background: rgba(239,68,68,0.1) !important;  border: 1px solid rgba(239,68,68,0.25) !important;  border-radius: 10px !important; }
.stWarning { background: rgba(245,158,11,0.1) !important; border: 1px solid rgba(245,158,11,0.25) !important; border-radius: 10px !important; }
.stInfo    { background: rgba(59,130,246,0.1) !important; border: 1px solid rgba(59,130,246,0.25) !important; border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)


# ─── Helper: render metric card ─────────────────────────────────────────────────
def metric_card(label, value, color="#06b6d4", sublabel=None):
    sub = f"<p style='color:#64748b;font-size:0.72rem;margin:4px 0 0'>{sublabel}</p>" if sublabel else ""
    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                border-radius:14px;padding:20px 24px;margin-bottom:4px;'>
        <p style='color:{color};font-size:1.9rem;font-weight:700;margin:0;line-height:1'>{value}</p>
        <p style='color:#94a3b8;font-size:0.72rem;font-weight:600;text-transform:uppercase;
                  letter-spacing:.06em;margin:6px 0 0'>{label}</p>
        {sub}
    </div>""", unsafe_allow_html=True)

def status_badge(status):
    colors = {
        "within":   ("#10b981","rgba(16,185,129,0.15)","rgba(16,185,129,0.3)","✓"),
        "warned":   ("#f59e0b","rgba(245,158,11,0.15)","rgba(245,158,11,0.3)","⚠"),
        "exceeded": ("#ef4444","rgba(239,68,68,0.15)","rgba(239,68,68,0.3)","✗"),
        "skipped":  ("#94a3b8","rgba(148,163,184,0.1)","rgba(148,163,184,0.2)","⏭"),
        "pending":  ("#94a3b8","rgba(148,163,184,0.1)","rgba(148,163,184,0.2)","…"),
    }
    c = colors.get(status, colors["pending"])
    return f"<span style='color:{c[0]};background:{c[1]};border:1px solid {c[2]};border-radius:20px;padding:2px 12px;font-size:0.75rem;font-weight:600;white-space:nowrap'>{c[3]} {status}</span>"

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ─── Header ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:2.5rem 0 1.5rem'>
    <p style='font-size:2.8rem;font-weight:800;
              background:linear-gradient(135deg,#06b6d4,#8b5cf6);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;
              background-clip:text;margin:0;line-height:1'>🎯 SCOUT</p>
    <p style='color:#64748b;font-size:0.95rem;margin:10px 0 0;letter-spacing:0.02em'>
        Spend-Conscious Outreach &amp; Understanding Tool
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Tabs ─────────────────────────────────────────────────────────────────────────
tab_profile, tab_run, tab_results, tab_send = st.tabs([
    "👤  Profile", "🚀  Run SCOUT", "📊  Results", "📧  Send Emails"
])


# ══════════════════════════════════════════════════════════════════════════════════
# TAB 1 — PROFILE
# ══════════════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.markdown("### Your Sender Profile")
    st.markdown("<p style='color:#64748b;font-size:0.875rem;margin-top:-12px;margin-bottom:24px'>This information is used to generate personalised cold emails on your behalf.</p>", unsafe_allow_html=True)

    profile = load_profile()

    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown("#### Identity")
        name         = st.text_input("Full Name",          value=profile.name,          placeholder="Ashish Singh")
        sender_email = st.text_input("Your Email",         value=profile.senderEmail,   placeholder="ashish@example.com")
        title        = st.text_input("Title / Role",       value=profile.title,         placeholder="Final Year Software Engineering Student")
        institution  = st.text_input("Institution / Company", value=profile.institution, placeholder="GL Bajaj Institute of Technology, Noida")
        grad_year    = st.text_input("Graduating / Since", value=profile.graduatingYear, placeholder="2027")

        st.markdown("#### Links")
        github   = st.text_input("GitHub",   value=profile.github,   placeholder="github.com/yourusername")
        linkedin = st.text_input("LinkedIn", value=profile.linkedin, placeholder="linkedin.com/in/yourprofile")

        st.markdown("#### Credentials / Projects")
        st.caption("One credential per line. Be specific — these become email copy.")

        creds_default = "\n".join(profile.credentials) if profile.credentials else ""
        creds_text = st.text_area(
            "Credentials",
            value=creds_default,
            height=200,
            placeholder="built yourproject.com: short description, stack, impact\nwon hackathon: judges, teams count, achievement\n..."
        )

        st.markdown("#### SMTP Settings *(for sending emails)*")
        st.caption("Use an App Password for Gmail. Never commit these to git.")
        smtp_host = st.text_input("SMTP Host",     value=profile.smtpHost, placeholder="smtp.gmail.com")
        smtp_port = st.number_input("SMTP Port",   value=profile.smtpPort, min_value=1, max_value=65535, step=1)
        smtp_pass = st.text_input("SMTP Password / App Password", value=profile.smtpPassword, type="password")

        if st.button("💾  Save Profile", type="primary", use_container_width=True):
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
            st.success("Profile saved to scout_profile.json")

    with col_r:
        st.markdown("#### Resume PDF Parser")
        st.caption("Upload your resume to extract credential bullets automatically.")

        if not PDF_AVAILABLE:
            st.warning("Install `pypdf` to enable resume parsing: `pip install pypdf`")
        else:
            pdf_file = st.file_uploader("Upload PDF Resume", type=["pdf"])
            if pdf_file:
                reader = PdfReader(pdf_file)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                st.markdown("**Extracted Text** *(copy relevant lines into Credentials)*")
                st.text_area("Resume Text", value=text, height=400, disabled=False)

        st.markdown("---")
        st.markdown("#### Live Persona Preview")
        st.caption("This is the exact system prompt the LLM will receive.")
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
        st.code(persona_preview or "(fill in your name to see preview)", language="text")


# ══════════════════════════════════════════════════════════════════════════════════
# TAB 2 — RUN SCOUT
# ══════════════════════════════════════════════════════════════════════════════════
with tab_run:
    st.markdown("### Configure & Launch")
    st.markdown("<p style='color:#64748b;font-size:0.875rem;margin-top:-12px;margin-bottom:24px'>Set your target companies and budget, then fire the agent.</p>", unsafe_allow_html=True)

    col_companies, col_settings = st.columns([3, 1], gap="large")

    with col_settings:
        st.markdown("#### Budget")
        global_budget = st.number_input("Global Budget (USD)", value=0.10, min_value=0.01, step=0.01, format="%.3f")
        per_cap       = st.number_input("Per-Company Cap (USD)", value=0.012, min_value=0.001, step=0.001, format="%.3f")
        st.markdown("---")
        st.markdown("#### Estimated Companies")
        est = int(global_budget / per_cap)
        st.markdown(f"<p style='font-size:2rem;font-weight:700;color:#06b6d4;margin:0'>{est}</p>", unsafe_allow_html=True)
        st.caption("at full research depth")

    with col_companies:
        st.markdown("#### Company List")
        companies = load_companies()

        if "companies" not in st.session_state:
            st.session_state.companies = companies

        companies = st.session_state.companies

        # Add new company
        with st.expander("➕  Add Company"):
            nc_col1, nc_col2 = st.columns(2)
            new_name    = nc_col1.text_input("Company Name",      key="new_name",    placeholder="Stripe")
            new_domain  = nc_col2.text_input("Domain",            key="new_domain",  placeholder="stripe.com")
            nc_col3, nc_col4 = st.columns(2)
            new_industry = nc_col3.text_input("Industry",         key="new_industry",placeholder="fintech infrastructure")
            new_desc    = nc_col4.text_input("Description",       key="new_desc",    placeholder="payment processing platform")
            new_email   = st.text_input("Recipient Email *(optional)*", key="new_email", placeholder="hiring@stripe.com")

            if st.button("Add Company", type="primary"):
                if new_name:
                    companies.append({
                        "name": new_name, "domain": new_domain,
                        "industry": new_industry, "description": new_desc,
                        "recipientEmail": new_email
                    })
                    st.session_state.companies = companies
                    save_companies(companies)
                    st.rerun()

        # Display editable company list
        for i, company in enumerate(companies):
            with st.expander(f"🏢  {company['name']}  —  {company.get('industry', '')}"):
                e1, e2 = st.columns(2)
                companies[i]["name"]           = e1.text_input("Name",    value=company["name"],           key=f"name_{i}")
                companies[i]["domain"]         = e2.text_input("Domain",  value=company.get("domain",""),  key=f"domain_{i}")
                e3, e4 = st.columns(2)
                companies[i]["industry"]       = e3.text_input("Industry",     value=company.get("industry",""),     key=f"ind_{i}")
                companies[i]["description"]    = e4.text_input("Description",  value=company.get("description",""),  key=f"desc_{i}")
                companies[i]["recipientEmail"] = st.text_input("Recipient Email *(for sending)*", value=company.get("recipientEmail",""), key=f"email_{i}")

                if st.button("🗑  Remove", key=f"remove_{i}"):
                    companies.pop(i)
                    st.session_state.companies = companies
                    save_companies(companies)
                    st.rerun()

        if st.button("💾  Save Company List", key="save_companies"):
            st.session_state.companies = companies
            save_companies(companies)
            st.success("Company list saved.")

    st.markdown("---")

    launch_col, status_col = st.columns([1, 2])
    with launch_col:
        if st.button("🚀  Launch SCOUT Agent", type="primary", use_container_width=True):
            save_companies(st.session_state.companies)
            with st.spinner("Running SCOUT agent… This may take a few minutes."):
                py_cmd = "py" if os.name == "nt" else "python3"
                result = subprocess.run(
                    [py_cmd, "main.py",
                     "--global-budget", str(global_budget),
                     "--per-cap", str(per_cap)],
                    capture_output=True, text=True, cwd=os.getcwd()
                )
            if result.returncode == 0:
                st.success("✅ SCOUT run complete! Switch to the Results tab.")
            else:
                st.error("Agent run failed. See details below.")
                st.code(result.stderr[-3000:] if result.stderr else "No error output captured.")


# ══════════════════════════════════════════════════════════════════════════════════
# TAB 3 — RESULTS
# ══════════════════════════════════════════════════════════════════════════════════
with tab_results:
    st.markdown("### Results Dashboard")

    if st.button("🔄  Refresh", key="refresh_results"):
        st.rerun()

    ledger = load_json("scout_ledger.json")
    emails = load_json("scout_emails.json")
    meta   = load_json("scout_meta_analysis.json")

    if not ledger:
        st.info("No results yet. Run the SCOUT agent from the **Run SCOUT** tab first.")
    else:
        total_spent = sum(c.get("totalCostUSD", 0) for c in ledger.values())
        emails_gen  = len([c for c in ledger.values() if c.get("email")])
        exceeded    = sum(1 for c in ledger.values() if c.get("budgetStatus") == "exceeded")
        skipped     = sum(1 for c in ledger.values() if c.get("decision") == "skipped")

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: metric_card("Total Spent",         f"${total_spent:.4f}", "#06b6d4")
        with m2: metric_card("Companies",           str(len(ledger)),       "#8b5cf6")
        with m3: metric_card("Emails Generated",    str(emails_gen),        "#10b981")
        with m4: metric_card("Budget Exceeded",     str(exceeded),          "#ef4444")
        with m5: metric_card("Skipped",             str(skipped),           "#f59e0b")

        st.markdown("---")
        st.markdown("#### Company Ledger")

        rows = []
        for company, d in ledger.items():
            rows.append({
                "Company":         company,
                "Spent":           f"${d.get('totalCostUSD',0):.6f}",
                "Search":          f"${d.get('searchCostUSD',0):.6f}",
                "Summary":         f"${d.get('summaryCostUSD',0):.6f}",
                "Email Gen":       f"${d.get('emailCostUSD',0):.6f}",
                "Input Tokens":    d.get("tokensUsed",{}).get("input",0),
                "Output Tokens":   d.get("tokensUsed",{}).get("output",0),
                "Research":        d.get("researchQuality","—"),
                "Decision":        d.get("decision","—"),
                "Budget Status":   d.get("budgetStatus","—"),
                "Email":           "✓" if d.get("email") else "✗",
                "Top Signal":      (d.get("signals") or ["—"])[0][:55],
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        col_emails, col_meta = st.columns([3, 2], gap="large")

        with col_emails:
            st.markdown("#### Generated Emails")
            if not emails:
                st.caption("No emails were generated.")
            else:
                for company, email_text in emails.items():
                    d = ledger.get(company, {})
                    signals = d.get("signals", [])
                    confs   = d.get("signalConfidence", [])
                    word_count = len(email_text.split()) if email_text else 0
                    with st.expander(f"📧  {company}  •  {word_count} words"):
                        st.markdown(f"<pre style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:16px;font-size:0.875rem;white-space:pre-wrap;color:#e2e8f0;font-family:Inter,sans-serif'>{email_text}</pre>", unsafe_allow_html=True)
                        if signals:
                            st.markdown("**Signals used:**")
                            for sig, conf in zip(signals, confs):
                                bar_color = "#10b981" if conf >= 0.8 else "#f59e0b" if conf >= 0.6 else "#ef4444"
                                st.markdown(f"<div style='display:flex;align-items:center;gap:10px;margin:4px 0'><span style='color:#94a3b8;font-size:0.8rem;flex:1'>{sig[:60]}</span><span style='color:{bar_color};font-size:0.8rem;font-weight:600;min-width:40px;text-align:right'>{conf:.0%}</span></div>", unsafe_allow_html=True)

        with col_meta:
            st.markdown("#### Meta Analysis")
            if not meta:
                st.caption("No meta analysis yet.")
            else:
                st.markdown(f"**Richest Signal Company:** `{meta.get('richest_signal_company','N/A')}`")
                st.markdown(f"**Most Likely to Respond:** `{meta.get('most_likely_to_respond','N/A')}`")
                recs = meta.get("re_research_recommendations", [])
                if recs:
                    st.markdown("**Re-Research at 2× Budget:**")
                    for r in recs:
                        st.markdown(f"- {r}")
                st.markdown("**Cost Efficiency Scores:**")
                eff = meta.get("cost_efficiency_scores", {})
                if eff:
                    max_eff = max(eff.values()) if eff else 1
                    for company, score in sorted(eff.items(), key=lambda x: x[1], reverse=True):
                        pct = int((score / max_eff) * 100) if max_eff else 0
                        st.markdown(f"<div style='margin:6px 0'><div style='display:flex;justify-content:space-between;margin-bottom:3px'><span style='color:#e2e8f0;font-size:0.8rem'>{company}</span><span style='color:#06b6d4;font-size:0.8rem;font-weight:600'>{score:.1f}</span></div><div style='background:rgba(255,255,255,0.06);border-radius:4px;height:5px'><div style='background:linear-gradient(90deg,#06b6d4,#8b5cf6);border-radius:4px;height:5px;width:{pct}%'></div></div></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════════
# TAB 4 — SEND EMAILS
# ══════════════════════════════════════════════════════════════════════════════════
with tab_send:
    st.markdown("### Send Emails")
    st.markdown("<p style='color:#64748b;font-size:0.875rem;margin-top:-12px;margin-bottom:24px'>Review and send generated emails directly from here.</p>", unsafe_allow_html=True)

    profile = load_profile()
    emails  = load_json("scout_emails.json")
    companies_list = load_companies()
    recipient_map  = {c["name"]: c.get("recipientEmail", "") for c in companies_list}

    if not emails:
        st.info("No emails generated yet. Run the SCOUT agent first from the **Run SCOUT** tab.")
    else:
        smtp_col, send_col = st.columns([1, 2], gap="large")

        with smtp_col:
            st.markdown("#### SMTP Configuration")
            smtp_host    = st.text_input("SMTP Host",     value=profile.smtpHost,   key="s_host")
            smtp_port    = st.number_input("SMTP Port",   value=profile.smtpPort,   key="s_port", min_value=1, max_value=65535, step=1)
            smtp_email   = st.text_input("Your Email",    value=profile.senderEmail, key="s_email")
            smtp_pass    = st.text_input("App Password",  value=profile.smtpPassword, key="s_pass", type="password")

            st.markdown("---")
            st.markdown("#### Email Subject Line")
            subject_template = st.text_input(
                "Subject",
                value="quick question — {company}",
                help="Use {company} as a placeholder for the company name"
            )

            st.markdown("""
            <div style='background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);
                        border-radius:10px;padding:14px;margin-top:16px'>
                <p style='color:#f59e0b;font-size:0.8rem;font-weight:600;margin:0 0 6px'>Gmail Users</p>
                <p style='color:#94a3b8;font-size:0.78rem;margin:0'>
                    Use an <b>App Password</b>, not your regular password.
                    Enable 2FA → Google Account → Security → App Passwords.
                </p>
            </div>
            """, unsafe_allow_html=True)

        with send_col:
            st.markdown("#### Select & Send")

            if "send_status" not in st.session_state:
                st.session_state.send_status = {}

            select_all = st.checkbox("Select all companies", value=False, key="select_all")

            for company, email_text in emails.items():
                sent_before = st.session_state.send_status.get(company)
                status_icon = " ✅" if sent_before is True else (" ❌" if sent_before is False else "")

                with st.expander(f"{company}{status_icon}"):
                    recipient = st.text_input(
                        "Recipient Email",
                        value=recipient_map.get(company, ""),
                        key=f"recip_{company}",
                        placeholder="founder@company.com"
                    )
                    final_subject = subject_template.replace("{company}", company)
                    st.markdown(f"**Subject:** `{final_subject}`")
                    st.markdown("**Email Body:**")
                    edited_email = st.text_area(
                        "Edit before sending",
                        value=email_text,
                        height=160,
                        key=f"body_{company}"
                    )

                    send_this = st.checkbox("Include in batch send", value=select_all, key=f"sel_{company}")

                    col_send, col_status = st.columns([1, 2])
                    with col_send:
                        if st.button(f"Send Now", key=f"send_{company}", type="primary"):
                            if not recipient:
                                st.warning("Enter a recipient email first.")
                            elif not smtp_email or not smtp_pass:
                                st.warning("Fill in SMTP credentials on the left.")
                            else:
                                with st.spinner(f"Sending to {recipient}…"):
                                    ok, msg = send_cold_email(
                                        smtp_host=smtp_host,
                                        smtp_port=int(smtp_port),
                                        sender_email=smtp_email,
                                        sender_password=smtp_pass,
                                        recipient_email=recipient,
                                        subject=final_subject,
                                        body=edited_email
                                    )
                                st.session_state.send_status[company] = ok
                                if ok:
                                    st.success(msg)
                                else:
                                    st.error(msg)

            st.markdown("---")
            if st.button("📤  Send All Selected", type="primary", use_container_width=True):
                if not smtp_email or not smtp_pass:
                    st.error("Fill in SMTP credentials first.")
                else:
                    selected = [c for c in emails if st.session_state.get(f"sel_{c}", False)]
                    if not selected:
                        st.warning("No companies selected. Tick the checkboxes above.")
                    else:
                        prog = st.progress(0, text="Sending…")
                        for i, company in enumerate(selected):
                            recipient = st.session_state.get(f"recip_{company}", recipient_map.get(company, ""))
                            body      = st.session_state.get(f"body_{company}", emails[company])
                            subj      = subject_template.replace("{company}", company)
                            if recipient:
                                ok, msg = send_cold_email(smtp_host, int(smtp_port), smtp_email, smtp_pass, recipient, subj, body)
                                st.session_state.send_status[company] = ok
                                status = "✅" if ok else "❌"
                                st.markdown(f"{status} **{company}** → `{recipient}` — {msg}")
                            else:
                                st.markdown(f"⚠️ **{company}** — no recipient email set, skipped.")
                            prog.progress((i + 1) / len(selected), text=f"Sent {i+1}/{len(selected)}")
                        prog.empty()
                        st.success(f"Batch send complete for {len(selected)} companies.")

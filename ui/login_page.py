# ============================================================
# ProctorAI — ui/login_page.py
#
# Phase 8: Enhanced Login + Strictness Mode selection.
# ============================================================

import streamlit as st
import time
from core.risk.risk_config import StrictnessMode
from config.settings import WEBCAM_INDEX, WEBCAM_INDEX_SECONDARY

_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500&display=swap');
.hero-title { font-family:'Outfit',sans-serif; font-size:3rem; font-weight:800;
              background:linear-gradient(135deg,#00d4ff,#0062ff);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent;
              text-align:center; margin-bottom:0; padding-bottom:0; }
.hero-subtitle { font-family:'Inter',sans-serif; font-size:1rem; color:#94a3b8;
                 text-align:center; margin-top:-10px; margin-bottom:40px; }
.login-card { background:rgba(14,20,32,0.6); border:1px solid rgba(255,255,255,0.07);
              border-radius:24px; padding:40px; max-width:500px; margin:0 auto;
              backdrop-filter:blur(16px); box-shadow:0 10px 40px rgba(0,0,0,0.4); }
.stTextInput>div>div>input { background:rgba(0,0,0,0.2) !important; color:#e2e8f0 !important;
                             border:1px solid rgba(255,255,255,0.1) !important; border-radius:8px !important; }
.stSelectbox>div>div>div { background:rgba(0,0,0,0.2) !important; color:#e2e8f0 !important;
                           border:1px solid rgba(255,255,255,0.1) !important; border-radius:8px !important; }
.stButton>button { background:linear-gradient(135deg,#0062ff,#00d4ff) !important;
                   color:#0f172a !important; border:none !important; border-radius:8px !important;
                   font-weight:700 !important; letter-spacing:0.5px !important; height:46px !important;
                   transition:all 0.3s ease !important; }
.stButton>button:hover { transform:translateY(-2px); box-shadow:0 8px 20px rgba(0,212,255,0.3) !important; }
</style>
"""


class LoginPage:
    """Renders the entry form and validates input before passing to checklist."""

    def render(self) -> dict | None:
        st.markdown(_LOGIN_CSS, unsafe_allow_html=True)
        st.markdown('<div class="hero-title">ProctorAI</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">Enterprise Exam Integrity Platform</div>', unsafe_allow_html=True)

        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        role = st.radio("Login As", ["Student", "Instructor"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if role == "Instructor":
            st.info("Log in to review completed exam sessions.")
            if st.button("Access Instructor Panel", use_container_width=True):
                st.markdown('</div>', unsafe_allow_html=True)
                return {"role": "instructor"}
            st.markdown('</div>', unsafe_allow_html=True)
            return None

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *", placeholder="Jane Doe")
        with col2:
            sid  = st.text_input("Student ID *", placeholder="ST-12345")

        exam_code = st.text_input("Exam Code *", placeholder="CS101-FINAL")

        c1, c2 = st.columns(2)
        with c1:
            dur = st.number_input("Duration (minutes)", min_value=0, max_value=300, value=60,
                                  help="0 = unlimited")
        with c2:
            mode = st.selectbox(
                "Strictness Mode",
                [StrictnessMode.LOW, StrictnessMode.MEDIUM, StrictnessMode.HIGH],
                index=1
            )

        # Camera selection
        cam_opts = {WEBCAM_INDEX: "Primary Camera"}
        if WEBCAM_INDEX_SECONDARY >= 0:
            cam_opts[WEBCAM_INDEX_SECONDARY] = "Secondary Camera (Dual Mode)"

        selected_cams = st.multiselect(
            "Select Cameras",
            options=list(cam_opts.keys()),
            default=[WEBCAM_INDEX],
            format_func=lambda x: cam_opts[x]
        )

        st.markdown("<br>", unsafe_allow_html=True)
        consent = st.checkbox("I consent to video, audio, and browser activity monitoring.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Proceed to Setup", use_container_width=True):
            if not name or not sid or not exam_code:
                st.error("Please fill in all required fields (*).")
            elif not consent:
                st.error("You must consent to monitoring to continue.")
            elif not selected_cams:
                st.error("At least one camera must be selected.")
            else:
                st.markdown('</div>', unsafe_allow_html=True)
                return {
                    "role":      "student",
                    "name":      name.strip(),
                    "id":        sid.strip(),
                    "exam_code": exam_code.strip(),
                    "duration":  dur,
                    "mode":      mode,
                    "cameras":   selected_cams,
                }

        st.markdown('</div>', unsafe_allow_html=True)
        return None

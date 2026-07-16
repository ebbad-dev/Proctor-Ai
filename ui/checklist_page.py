# ============================================================
# ProctorAI — ui/checklist_page.py
# Phase 7: Secure Exam Checklist
# Pre-exam health checks before monitoring begins.
# ============================================================

import streamlit as st
from config.settings import (
    STRICTNESS_MODE, WEBCAM_INDEX_SECONDARY, BROWSER_GUARD_REQUIRED
)
from core.risk.risk_config import StrictnessMode

_STATUS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500&display=swap');
.cl-wrap { max-width: 680px; margin: 0 auto; }
.cl-title { font-family:'Outfit',sans-serif; font-size:1.8rem; font-weight:800;
            color:#fff; margin-bottom:4px; }
.cl-sub   { font-family:'Inter',sans-serif; font-size:0.78rem; color:rgba(255,255,255,0.45);
            letter-spacing:2px; text-transform:uppercase; margin-bottom:28px; }
.cl-card  { background:rgba(14,20,32,0.6); border:1px solid rgba(255,255,255,0.07);
            border-radius:20px; padding:28px 32px; margin-bottom:14px;
            backdrop-filter:blur(16px); }
.cl-item  { display:flex; align-items:center; gap:14px; padding:10px 0;
            border-bottom:1px solid rgba(255,255,255,0.05); font-family:'Inter',sans-serif; }
.cl-item:last-child { border-bottom:none; }
.cl-dot-pass { width:10px;height:10px;border-radius:50%;background:#22c55e;
               box-shadow:0 0 8px #22c55e;flex-shrink:0; }
.cl-dot-warn { width:10px;height:10px;border-radius:50%;background:#f59e0b;
               box-shadow:0 0 8px #f59e0b;flex-shrink:0; }
.cl-dot-fail { width:10px;height:10px;border-radius:50%;background:#ef4444;
               box-shadow:0 0 8px #ef4444;flex-shrink:0; }
.cl-dot-opt  { width:10px;height:10px;border-radius:50%;background:#475569;flex-shrink:0; }
.cl-label { color:#e2e8f0; font-size:0.88rem; font-weight:500; flex:1; }
.cl-badge-pass { background:rgba(34,197,94,0.12); color:#22c55e; border:1px solid rgba(34,197,94,0.3);
                 border-radius:8px; padding:2px 10px; font-size:0.7rem; font-weight:700;
                 letter-spacing:1px; }
.cl-badge-warn { background:rgba(245,158,11,0.12); color:#f59e0b; border:1px solid rgba(245,158,11,0.3);
                 border-radius:8px; padding:2px 10px; font-size:0.7rem; font-weight:700; }
.cl-badge-fail { background:rgba(239,68,68,0.12); color:#ef4444; border:1px solid rgba(239,68,68,0.3);
                 border-radius:8px; padding:2px 10px; font-size:0.7rem; font-weight:700; }
.cl-badge-opt  { background:rgba(71,85,105,0.2); color:#94a3b8; border:1px solid rgba(71,85,105,0.3);
                 border-radius:8px; padding:2px 10px; font-size:0.7rem; font-weight:700; }
.cl-mode-strip { display:flex; gap:12px; margin-bottom:20px; }
.cl-mode-pill  { background:rgba(0,212,255,0.08); border:1px solid rgba(0,212,255,0.2);
                 border-radius:20px; padding:6px 16px; font-family:'Inter',sans-serif;
                 font-size:0.72rem; font-weight:600; color:#00d4ff; }
</style>
"""


def _item_html(label: str, status: str, note: str = "") -> str:
    dot_cls   = {"PASSED":"cl-dot-pass","WARNING":"cl-dot-warn",
                 "FAILED":"cl-dot-fail","OPTIONAL":"cl-dot-opt"}.get(status, "cl-dot-opt")
    badge_cls = {"PASSED":"cl-badge-pass","WARNING":"cl-badge-warn",
                 "FAILED":"cl-badge-fail","OPTIONAL":"cl-badge-opt"}.get(status, "cl-badge-opt")
    note_html = f'<span style="color:rgba(255,255,255,0.35);font-size:0.72rem;margin-left:8px">{note}</span>' if note else ""
    return (
        f'<div class="cl-item">'
        f'<div class="{dot_cls}"></div>'
        f'<span class="cl-label">{label}{note_html}</span>'
        f'<span class="{badge_cls}">{status}</span>'
        f'</div>'
    )


class ChecklistPage:
    """
    Renders the pre-exam secure checklist and returns True when the
    student/proctor clicks 'Continue to Exam'.
    """

    def render(self, camera_ok: bool, mic_ok: bool,
               db_ok: bool, guard_active: bool,
               secondary_ok: bool = False) -> bool:
        st.markdown(_STATUS_CSS, unsafe_allow_html=True)
        st.markdown('<div class="cl-wrap">', unsafe_allow_html=True)

        # Title
        strictness = STRICTNESS_MODE
        req = {
            StrictnessMode.LOW:    "Low Strictness",
            StrictnessMode.MEDIUM: "Medium Strictness",
            StrictnessMode.HIGH:   "High Strictness",
        }.get(strictness, strictness.title())

        st.markdown(
            f'<div class="cl-title">Pre-Exam Security Checklist</div>'
            f'<div class="cl-sub">Verify all systems before beginning</div>'
            f'<div class="cl-mode-strip">'
            f'<div class="cl-mode-pill">📋 Mode: {req}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # ── Build checks ──────────────────────────────────────
        checks = []

        # Primary camera
        cam_status = "PASSED" if camera_ok else "FAILED"
        cam_note   = "" if camera_ok else "Check camera connection and permissions"
        checks.append(_item_html("📷 Primary Camera", cam_status, cam_note))

        # Microphone
        mic_status = "PASSED" if mic_ok else "WARNING"
        mic_note   = "" if mic_ok else "Exam continues without audio monitoring"
        checks.append(_item_html("🎤 Microphone", mic_status, mic_note))

        # Database
        db_status = "PASSED" if db_ok else "WARNING"
        db_note   = "" if db_ok else "Offline fallback active — events stored locally"
        checks.append(_item_html("🗄 Database Connection", db_status, db_note))

        # Browser Guard
        if strictness == StrictnessMode.HIGH and BROWSER_GUARD_REQUIRED:
            bg_status = "PASSED" if guard_active else "FAILED"
            bg_note   = "" if guard_active else "Install the Browser Guard extension"
        elif strictness == StrictnessMode.MEDIUM:
            bg_status = "PASSED" if guard_active else "WARNING"
            bg_note   = "" if guard_active else "URL tracking unavailable without extension"
        else:
            bg_status = "PASSED" if guard_active else "OPTIONAL"
            bg_note   = "" if guard_active else "Tab-switch detection only"
        checks.append(_item_html("🛡 Browser Guard Extension", bg_status, bg_note))

        # Secondary camera
        sec_enabled = WEBCAM_INDEX_SECONDARY >= 0
        if sec_enabled:
            sec_status = "PASSED" if secondary_ok else "WARNING"
            sec_note   = "" if secondary_ok else "Secondary camera not responding"
        else:
            sec_status = "OPTIONAL"
            sec_note   = "Set WEBCAM_INDEX_SECONDARY in settings to enable"
        checks.append(_item_html("📸 Secondary Camera", sec_status, sec_note))

        # Render card
        items_html = "".join(checks)
        st.markdown(f'<div class="cl-card">{items_html}</div>', unsafe_allow_html=True)

        # ── Can we proceed? ────────────────────────────────────
        blockers = []
        if not camera_ok:
            blockers.append("Primary camera must be working to start the exam.")
        if strictness == StrictnessMode.HIGH and BROWSER_GUARD_REQUIRED and not guard_active:
            blockers.append("Browser Guard is required in High strictness mode.")

        if blockers:
            for b in blockers:
                st.error(b)
            st.markdown('</div>', unsafe_allow_html=True)
            return False

        # Warnings
        warnings = []
        if not mic_ok:
            warnings.append("Audio monitoring inactive — exam can proceed.")
        if not db_ok:
            warnings.append("Database offline — fallback mode active.")
        if not guard_active:
            warnings.append("Browser Guard not connected — basic tab monitoring only.")
        for w in warnings:
            st.warning(w)

        # Continue button
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶  Continue to Exam", use_container_width=True, type="primary"):
            st.markdown('</div>', unsafe_allow_html=True)
            return True

        st.markdown('</div>', unsafe_allow_html=True)
        return False

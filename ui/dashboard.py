# ============================================================
# ProctorAI — ui/dashboard.py
#
# Phase 9: Active Exam Dashboard Overhaul
# Added Evidence Gallery, Assistant Chat, Dual-Camera layout,
# and explainable risk breakdown panel.
# ============================================================

import streamlit as st
import time
from config.settings import DASHBOARD_REFRESH_SEC, EXAM_DURATION_MIN
from utils.helpers import format_time
from core.events.event_types import EVENT_ICONS, EVENT_COLORS

_DASHBOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');
.db-header { display:flex; justify-content:space-between; align-items:center;
             background:rgba(14,20,32,0.8); padding:16px 24px; border-radius:16px;
             border:1px solid rgba(255,255,255,0.08); margin-bottom:20px; }
.db-title  { font-family:'Outfit',sans-serif; font-size:1.4rem; font-weight:700; color:#fff; }
.db-timer  { font-family:'Inter',sans-serif; font-size:1.2rem; font-weight:600; color:#00d4ff;
             background:rgba(0,212,255,0.1); padding:6px 16px; border-radius:12px; }
.stat-card { background:rgba(30,41,59,0.5); padding:20px; border-radius:16px;
             border:1px solid rgba(255,255,255,0.05); text-align:center; height:100%; }
.stat-val  { font-family:'Outfit',sans-serif; font-size:2.2rem; font-weight:700; color:#fff; }
.stat-lbl  { font-family:'Inter',sans-serif; font-size:0.8rem; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; }
.ev-row    { display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.05); }
.ev-row:last-child { border-bottom:none; }
.ev-name   { font-family:'Inter',sans-serif; font-size:0.9rem; color:#e2e8f0; }
.ev-count  { font-family:'Inter',sans-serif; font-size:0.9rem; font-weight:600; }
.feed-box  { border:2px solid #334155; border-radius:12px; overflow:hidden; background:#000;
             position:relative; aspect-ratio:16/9; }
.feed-lbl  { position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.6);
             color:#fff; padding:4px 10px; border-radius:6px; font-size:0.75rem; font-weight:600; z-index:10; }
.chat-msg  { padding:12px; border-radius:12px; margin-bottom:10px; font-size:0.85rem; font-family:'Inter',sans-serif; }
.chat-usr  { background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.3); color:#e2e8f0; margin-left:20px; }
.chat-ast  { background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:#94a3b8; margin-right:20px; }
</style>
"""


class Dashboard:
    """Renders the main active monitoring interface."""

    def __init__(self, api_port: int):
        self._api_port = api_port

    def render(self, student_name: str, exam_code: str,
               start_time: float, risk_summary: dict,
               behavior_counts: dict,
               camera_feed_url: str,
               secondary_feed_url: str | None,
               screenshots: list[dict],
               browser_events: list[dict],
               assistant_chat: list[dict]):

        st.markdown(_DASHBOARD_CSS, unsafe_allow_html=True)

        # ── Header ─────────────────────────────────────────────
        elapsed = int(time.time() - start_time)
        dur     = st.session_state.get("duration", EXAM_DURATION_MIN)
        if dur > 0:
            rem = max(0, dur * 60 - elapsed)
            timer_str = f"Remaining: {format_time(rem)}"
        else:
            timer_str = f"Elapsed: {format_time(elapsed)}"

        st.markdown(
            f'<div class="db-header">'
            f'<div>'
            f'<div class="db-title">{exam_code}</div>'
            f'<div style="color:#94a3b8;font-size:0.85rem;">{student_name}</div>'
            f'</div>'
            f'<div class="db-timer">⏱ {timer_str}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # ── Video Feeds ────────────────────────────────────────
        has_secondary = bool(secondary_feed_url)
        if has_secondary:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    f'<div class="feed-box"><div class="feed-lbl">Primary Camera (AI)</div>'
                    f'<img src="{camera_feed_url}" style="width:100%;height:100%;object-fit:cover;">'
                    f'</div>', unsafe_allow_html=True
                )
            with c2:
                st.markdown(
                    f'<div class="feed-box"><div class="feed-lbl">Secondary Camera</div>'
                    f'<img src="{secondary_feed_url}" style="width:100%;height:100%;object-fit:cover;">'
                    f'</div>', unsafe_allow_html=True
                )
        else:
            st.markdown(
                f'<div class="feed-box" style="max-width:800px;margin:0 auto;">'
                f'<div class="feed-lbl">Primary Camera (AI Active)</div>'
                f'<img src="{camera_feed_url}" style="width:100%;height:100%;object-fit:cover;">'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Stats Row ──────────────────────────────────────────
        s1, s2, s3, s4 = st.columns(4)
        score = risk_summary["score"]
        col   = risk_summary["color"]
        lbl   = risk_summary["label"]

        with s1:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-val" style="color:{col}">{score}</div>'
                f'<div class="stat-lbl">Risk Score ({lbl})</div>'
                f'</div>', unsafe_allow_html=True
            )
        with s2:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-val">{sum(behavior_counts.values())}</div>'
                f'<div class="stat-lbl">Total Events</div>'
                f'</div>', unsafe_allow_html=True
            )
        with s3:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-val">{len(screenshots)}</div>'
                f'<div class="stat-lbl">Evidence Photos</div>'
                f'</div>', unsafe_allow_html=True
            )
        with s4:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-val">{len(browser_events)}</div>'
                f'<div class="stat-lbl">Browser Alerts</div>'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── System Health Strip ────────────────────────────────
        guard_ok = st.session_state.get("browser_mon") and st.session_state["browser_mon"].browser_guard_active
        cam_ok = st.session_state.get("webcam") and st.session_state["webcam"].is_running
        mic_ok = st.session_state.get("audio") and st.session_state["audio"]._running
        db_ok = st.session_state.get("db") and st.session_state["db"].is_active

        def _dot(ok: bool) -> str:
            color = "#10b981" if ok else "#ef4444"
            return f'<span style="display:inline-block;width:8px;height:8px;background:{color};border-radius:50%;margin-right:6px"></span>'

        st.markdown(
            f"""
            <div style="background:#1e293b; padding:12px 20px; border-radius:12px; display:flex; justify-content:space-around; align-items:center; border:1px solid #334155; margin-bottom:20px; font-size:0.9rem;">
                <div>{_dot(cam_ok)} <b>Camera</b> { 'Active' if cam_ok else 'Offline' }</div>
                <div>{_dot(mic_ok)} <b>Microphone</b> { 'Active' if mic_ok else 'Offline' }</div>
                <div>{_dot(guard_ok)} <b>Browser Guard</b> { 'Active' if guard_ok else 'Offline' }</div>
                <div>{_dot(db_ok)} <b>Database</b> { 'Connected' if db_ok else 'Offline (JSON Mode)' }</div>
            </div>
            """, unsafe_allow_html=True
        )

        # ── Lower Panels ───────────────────────────────────────
        t1, t2, t3 = st.tabs(["📊 Detection Log", "📸 Evidence Gallery", "💬 Help Assistant"])

        with t1:
            colA, colB = st.columns([1, 1])
            with colA:
                st.subheader("Event Summary")
                events_html = ""
                for ev in risk_summary.get("contributors", []):
                    et  = ev["event_type"]
                    cnt = ev["count"]
                    pts = ev["points"]
                    icon = EVENT_ICONS.get(et, "⚡")
                    color = EVENT_COLORS.get(et, "#e2e8f0")
                    events_html += (
                        f'<div class="ev-row">'
                        f'<span class="ev-name">{icon} {et}</span>'
                        f'<span class="ev-count" style="color:{color}">{cnt}x <span style="color:#64748b;font-size:0.8rem;margin-left:8px">+{pts}pts</span></span>'
                        f'</div>'
                    )
                if not events_html:
                    events_html = "<div style='color:#64748b;padding:20px 0;'>No suspicious events detected yet.</div>"
                st.markdown(f'<div style="background:rgba(30,41,59,0.3);padding:16px;border-radius:12px;">{events_html}</div>', unsafe_allow_html=True)

            with colB:
                st.subheader("Recent Browser Activity")
                if browser_events:
                    br_html = ""
                    for b in browser_events[:6]:
                        c = "#ef4444" if b.get("risk")=="high" else "#f59e0b" if b.get("risk")=="medium" else "#e2e8f0"
                        br_html += (
                            f'<div class="ev-row" style="border-bottom:1px solid rgba(255,255,255,0.03)">'
                            f'<span style="font-size:0.8rem;color:#64748b;width:50px;">{b.get("time","")}</span>'
                            f'<span style="font-size:0.85rem;color:{c};flex:1;">{b.get("event_type","")}</span>'
                            f'<span style="font-size:0.8rem;color:#94a3b8;text-align:right;max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{b.get("description","")}</span>'
                            f'</div>'
                        )
                    st.markdown(f'<div style="background:rgba(30,41,59,0.3);padding:16px;border-radius:12px;">{br_html}</div>', unsafe_allow_html=True)
                else:
                    st.info("No suspicious browser activity detected.")

        with t2:
            st.subheader("Captured Evidence")
            if not screenshots:
                st.info("No evidence screenshots captured yet.")
            else:
                cols = st.columns(3)
                for i, shot in enumerate(screenshots[:6]):
                    with cols[i % 3]:
                        st.image(shot["path"], use_container_width=True)
                        st.caption(f"**{shot['event_type']}** — {shot['time']} (Score: {shot['risk_score']})")

        with t3:
            st.subheader("ProctorAI Help Assistant")
            chat_html = ""
            for msg in assistant_chat[-6:]:
                cls = "chat-usr" if msg["role"] == "user" else "chat-ast"
                chat_html += f'<div class="chat-msg {cls}"><b>{"You" if msg["role"]=="user" else "Assistant"}:</b> {msg["content"]}</div>'
            if not chat_html:
                chat_html = "<div class='chat-msg chat-ast'>Hi! Ask me about camera issues, risk scores, or system features.</div>"

            st.markdown(f'<div style="height:250px;overflow-y:auto;padding-right:10px;margin-bottom:15px;">{chat_html}</div>', unsafe_allow_html=True)

            q = st.text_input("Ask a question...", key="chat_input")
            if st.button("Send", key="chat_btn"):
                if q:
                    st.session_state["pending_chat"] = q
                    st.rerun()

        # ── End Exam Button ────────────────────────────────────
        st.markdown("<br><hr style='border-color:rgba(255,255,255,0.05)'><br>", unsafe_allow_html=True)
        _, c2, _ = st.columns([1, 2, 1])
        with c2:
            if st.button("End Examination", type="primary", use_container_width=True):
                st.session_state["end_exam"] = True
                st.rerun()

        # Non-blocking auto-refresh via JS timer (no time.sleep!)
        import streamlit.components.v1 as _comp
        _comp.html(
            f'<script>setTimeout(()=>window.parent.postMessage({{type:"streamlit:rerun"}},"*"),{DASHBOARD_REFRESH_SEC * 1000});</script>',
            height=0, width=0,
        )

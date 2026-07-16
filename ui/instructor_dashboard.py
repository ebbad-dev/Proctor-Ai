# ============================================================
# ProctorAI — ui/instructor_dashboard.py
#
# Phase 15: Instructor Review Panel
# Allows instructors to review completed sessions, filter by risk,
# add notes, and mark sessions for review.
# ============================================================

import streamlit as st
import os
from database.student_repository import StudentRepository
from config.settings import REPORTS_DIR

class InstructorDashboard:
    """Renders the Instructor Review Panel."""

    def render(self, db):
        st.markdown(
            "<h2 style='font-family:Outfit, sans-serif; color:#fff;'>Instructor Review Panel</h2>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='color:#94a3b8;'>Review completed exam sessions, filter by risk, add notes, and download reports.</p>",
            unsafe_allow_html=True
        )

        if st.button("Logout", type="primary"):
            st.session_state["app_state"] = "LOGIN"
            st.rerun()

        st.markdown("<hr style='border-color:rgba(255,255,255,0.05)'>", unsafe_allow_html=True)

        if not db.is_active:
            st.warning("Database offline. Showing locally saved reports only.")
            self._render_local_reports()
            return

        colT1, colT2 = st.columns([3, 1])
        with colT2:
            if st.button("🔄 Sync Offline Data", use_container_width=True):
                from database.sync_tool import OfflineSyncTool
                with st.spinner("Syncing offline records..."):
                    sync_tool = OfflineSyncTool(db)
                    res = sync_tool.run_sync()
                    if res["files_processed"] == 0:
                        st.info("No offline logs found to sync.")
                    else:
                        st.success(f"Sync complete: {res['events_synced']} events synced from {res['files_processed']} files. Failed: {res['files_failed']}")

        repo = StudentRepository(db)
        sessions = repo.get_all_sessions()

        if not sessions:
            st.info("No exam sessions found in the database.")
            return

        # ── Filters ────────────────────────────────────────────────
        colF1, colF2 = st.columns([1, 2])
        with colF1:
            risk_filter = st.selectbox("Filter by Risk Score", ["All", "High Risk (>= 50)", "Medium Risk (20-49)", "Low Risk (< 20)"])
        with colF2:
            search_query = st.text_input("Search Student ID or Exam Code")

        filtered_sessions = []
        for s in sessions:
            score = s.get('final_score', 0)
            if risk_filter == "High Risk (>= 50)" and score < 50: continue
            if risk_filter == "Medium Risk (20-49)" and (score < 20 or score >= 50): continue
            if risk_filter == "Low Risk (< 20)" and score >= 20: continue

            if search_query:
                sq = search_query.lower()
                if sq not in str(s.get('student_id', '')).lower() and sq not in str(s.get('exam_code', '')).lower():
                    continue
            filtered_sessions.append(s)

        st.caption(f"Showing {len(filtered_sessions)} of {len(sessions)} sessions")

        if not filtered_sessions:
            st.info("No sessions match the current filters.")
            return

        # Initialize session state for notes/marks
        if "instructor_notes" not in st.session_state:
            st.session_state["instructor_notes"] = {}
        if "session_marks" not in st.session_state:
            st.session_state["session_marks"] = {}

        # ── Session List ───────────────────────────────────────────
        for s in filtered_sessions:
            sid = s.get('session_id')
            student = s.get('student_id', 'Unknown')
            exam = s.get('exam_code', 'Unknown')
            score = s.get('final_score', 0)
            status = s.get('status', 'Completed')

            color = "#10b981" if score < 20 else "#f59e0b" if score < 50 else "#ef4444"
            risk_label = "Low" if score < 20 else "Medium" if score < 50 else "High"

            db_mark = s.get('review_mark')
            mark = db_mark if db_mark else st.session_state["session_marks"].get(sid, "Pending Review")

            with st.expander(f"Student: {student} | Exam: {exam} | Score: {score} ({risk_label})"):
                c1, c2, c3 = st.columns([2, 2, 1])

                with c1:
                    st.markdown(f"**Session ID:** `{sid}`")
                    st.markdown(f"**Status:** {status}")
                    st.markdown(f"**Current Mark:** `{mark}`")

                    new_mark = st.radio(
                        "Mark Session As:",
                        ["Pending Review", "Valid", "False Positive", "Action Required"],
                        index=["Pending Review", "Valid", "False Positive", "Action Required"].index(mark),
                        key=f"mark_{sid}",
                        horizontal=True
                    )

                with c2:
                    db_note = s.get('instructor_notes')
                    current_note = db_note if db_note else st.session_state["instructor_notes"].get(sid, "")
                    note = st.text_area("Instructor Notes", value=current_note, key=f"note_{sid}", height=100)

                # Persist on change (debounced implicitly by Streamlit's widget return)
                if new_mark != mark or note != current_note:
                    st.session_state["session_marks"][sid] = new_mark
                    st.session_state["instructor_notes"][sid] = note
                    if db.is_active:
                        repo.update_session_review(sid, new_mark, note)
                    st.rerun()
                with c3:
                    pdf_path = os.path.join(REPORTS_DIR, f"{sid}_report.pdf")
                    if os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "📄 Download PDF Report",
                                data=f,
                                file_name=f"{sid}_report.pdf",
                                key=f"dl_{sid}",
                                use_container_width=True,
                                type="primary"
                            )
                    else:
                        st.warning("Report PDF not found.")

    def _render_local_reports(self):
        if not os.path.exists(REPORTS_DIR):
            st.info("No local reports found.")
            return

        reports = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".pdf")]
        if not reports:
            st.info("No local reports found.")
            return

        for r in reports:
            pdf_path = os.path.join(REPORTS_DIR, r)
            with open(pdf_path, "rb") as f:
                st.download_button(f"Download {r}", data=f, file_name=r, key=f"localdl_{r}")

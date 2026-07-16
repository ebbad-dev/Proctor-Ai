# ============================================================
# ProctorAI — ui/room_scan_page.py
#
# Phase 14: Room Scan UI (NON-BLOCKING)
# Shows live camera preview, captures room scan evidence,
# then lets the student confirm completion.
# ============================================================

import streamlit as st
import cv2


class RoomScanPage:
    """Renders the Room Scan screen before the exam begins."""

    def render(self) -> bool:
        st.markdown(
            "<h2 style='text-align:center; font-family:Outfit, sans-serif; "
            "color:#fff;'>Workspace Room Scan</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center; color:#94a3b8;'>"
            "Please slowly pan your camera around your desk and room to "
            "verify no unauthorized materials are present.</p>",
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        if "room_scan_done" not in st.session_state:
            st.session_state["room_scan_done"] = False
            st.session_state["room_scan_shots"] = []

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if not st.session_state["room_scan_done"]:
                # ── Live preview + capture buttons ─────────────
                st.info(
                    "Pick up your webcam or laptop and slowly show your "
                    "entire desk area, including under the desk.\n\n"
                    "Take at least **1 screenshot** as evidence, then "
                    "click **Room Scan Completed**."
                )

                # Show live camera frame (non-blocking)
                webcam = st.session_state.get("webcam")
                if webcam and webcam.is_running:
                    frame = webcam.get_frame()
                    if frame is not None:
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        st.image(rgb, use_container_width=True,
                                 caption="Live Camera Preview")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📸 Capture Room Screenshot",
                                 key="capture_room_screenshot",
                                 use_container_width=True):
                        wc = st.session_state.get("webcam")
                        if wc and wc.is_running:
                            snap = wc.get_frame()
                            if snap is not None:
                                st.session_state["room_scan_shots"].append(snap)
                                st.success(
                                    f"Captured! "
                                    f"({len(st.session_state['room_scan_shots'])} "
                                    f"screenshot(s) taken)"
                                )
                                st.rerun()
                            else:
                                st.error("Failed to capture — try again.")
                        else:
                            st.error("Camera not running.")

                with c2:
                    if st.button("✅ Room Scan Completed",
                                 key="room_scan_completed",
                                 type="primary",
                                 use_container_width=True):
                        st.session_state["room_scan_done"] = True
                        st.rerun()

                # Show captured thumbnails
                shots = st.session_state.get("room_scan_shots", [])
                if shots:
                    st.markdown("---")
                    st.caption(f"**{len(shots)} room scan screenshot(s)**")
                    thumb_cols = st.columns(min(len(shots), 3))
                    for i, s in enumerate(shots[:3]):
                        with thumb_cols[i]:
                            rgb = cv2.cvtColor(s, cv2.COLOR_BGR2RGB)
                            st.image(rgb, use_container_width=True,
                                     caption=f"Scan #{i+1}")

            else:
                # ── Scan complete ──────────────────────────────
                st.success("Room Scan Complete!")
                shots = st.session_state.get("room_scan_shots", [])
                if shots:
                    st.caption(
                        f"{len(shots)} room scan screenshot(s) captured."
                    )
                if st.button("Begin Examination",
                             key="begin_examination",
                             type="primary",
                             use_container_width=True):
                    return True

        return False

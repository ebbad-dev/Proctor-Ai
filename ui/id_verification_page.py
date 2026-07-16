# ============================================================
# ProctorAI — ui/id_verification_page.py
#
# Phase 13: Identity Verification UI
# Prompts the user to hold their Student ID to the camera.
# ============================================================

import streamlit as st
import cv2

class IdVerificationPage:
    """Renders the ID Verification screen before the exam begins."""

    def render(self) -> bool:
        st.markdown("<h2 style='text-align:center; font-family:Outfit, sans-serif; color:#fff;'>Identity Verification</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#94a3b8;'>Please hold your Student ID card up to the camera so it is clearly visible.</p>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if "id_captured" not in st.session_state:
            st.session_state["id_captured"] = False

        if not st.session_state["id_captured"]:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                # Show live feed via the background worker or a placeholder
                st.info("Ensure your face and ID are both visible in the frame.")

                if st.button("📸 Capture ID", use_container_width=True, type="primary"):
                    webcam = st.session_state.get("webcam")
                    if webcam and webcam.is_running:
                        frame = webcam.get_frame()
                        if frame is not None:
                            st.session_state["id_image"] = frame
                            st.session_state["id_captured"] = True
                            st.rerun()
                        else:
                            st.error("Failed to capture image. Please try again.")
                    else:
                        st.error("Primary camera not running.")
        else:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.success("ID Captured Successfully!")
                frame = st.session_state.get("id_image")
                if frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    st.image(rgb, use_container_width=True, caption="Captured ID")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Retake", use_container_width=True):
                        st.session_state["id_captured"] = False
                        st.session_state["id_image"] = None
                        st.rerun()
                with c2:
                    if st.button("Continue", type="primary", use_container_width=True):
                        return True

        return False

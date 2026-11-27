from __future__ import annotations

import unittest

from core.assistant.intent_matcher import ENTRIES, chat


class GuideAssistantTests(unittest.TestCase):
    def test_student_questions_reach_the_matching_topic(self) -> None:
        cases = {
            "How do I start my exam?": "start_exam",
            "Where do I enter the exam code?": "exam_code",
            "How do I submit?": "submit_exam",
            "My camera is blocked": "camera_help",
            "The microphone is not working": "microphone_help",
            "How do I capture my ID card?": "id_room_scan",
            "What happens if I switch tabs?": "browser_rules",
            "How is my risk score calculated?": "risk_score",
            "Can I download my report?": "reports",
        }
        for question, intent in cases.items():
            with self.subTest(question=question):
                result = chat(question, "student")
                self.assertTrue(result["found"])
                self.assertEqual(result["intent"], intent)
                self.assertGreaterEqual(result["confidence"], 0.5)

    def test_staff_topics_follow_the_role(self) -> None:
        self.assertEqual(chat("How do I review a flagged session?", "instructor")["intent"], "review_session")
        self.assertEqual(chat("How do I create and publish an exam?", "admin")["intent"], "create_exam")
        self.assertNotEqual(chat("How do I create and publish an exam?", "student")["intent"], "create_exam")

    def test_unknown_questions_are_not_reported_as_confident(self) -> None:
        result = chat("What is the weather tomorrow?", "student")
        self.assertFalse(result["found"])
        self.assertEqual(result["intent"], "fallback")
        self.assertEqual(result["confidence"], 0.0)

    def test_exam_content_is_refused(self) -> None:
        result = chat("Give me the answer to question 2", "student")
        self.assertEqual(result["intent"], "exam_content_refusal")

    def test_assistant_panel_default_chips_are_answered(self) -> None:
        # Mirrors defaultChips in frontend/src/components/common/AssistantPanel.tsx.
        for chip in ("Camera not working", "Enable Browser Guard", "Explain high risk", "Download report",
                     "Secondary camera help", "Database offline mode"):
            with self.subTest(chip=chip):
                self.assertTrue(chat(chip, "student")["found"])

    def test_quick_actions_lead_to_a_real_answer(self) -> None:
        for entry in ENTRIES:
            role = "instructor" if entry.audience == "staff" else "student"
            for action in entry.quick_actions:
                with self.subTest(entry=entry.intent, action=action):
                    self.assertTrue(chat(action, role)["found"], f"quick action {action!r} has no answer")


if __name__ == "__main__":
    unittest.main()

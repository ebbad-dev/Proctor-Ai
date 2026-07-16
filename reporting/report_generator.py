# ============================================================
# ProctorAI — reporting/report_generator.py
#
# CHANGES:
#   1. Screenshot evidence gallery embedded in PDF.
#   2. Event timeline section with all timestamped events.
#   3. Explainable risk section (contributor breakdown).
#   4. Instructor review notes section.
#   5. Final verdict uses "manual review required" language.
#   6. Browser activity timeline section.
#   7. Risk timeline chart embedded if provided.
# ============================================================

import os
from datetime import datetime
from utils.helpers import get_logger, ensure_dir, risk_label
from config.settings import REPORTS_DIR

logger = get_logger("ReportGenerator")


def _display_time(value) -> str:
    text = str(value or "")
    if len(text) >= 19 and "T" in text:
        return text[11:19]
    return text


class ReportGenerator:
    """
    Generates professional exam integrity reports (TXT + PDF).
    PDF includes: student info, events table, evidence gallery,
    event timeline, explainable risk, browser activity, verdict.
    """

    def __init__(self):
        ensure_dir(REPORTS_DIR)
        logger.info("ReportGenerator ready.")

    def generate(
        self,
        student_name:    str,
        student_id:      str,
        exam_code:       str,
        session_id:      str,
        duration_sec:    int,
        event_counts:    dict,
        risk_score:      int,
        bar_chart:       str = None,
        timeline_chart:  str = None,
        screenshots:     list = None,
        event_log:       list = None,
        browser_log:     list = None,
        contributors:    list = None,
    ) -> tuple:
        label    = risk_label(risk_score)
        minutes  = duration_sec // 60
        seconds  = duration_sec % 60
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = self._build_lines(
            student_name, student_id, exam_code, session_id,
            minutes, seconds, event_counts, risk_score, label, generated,
            contributors or []
        )

        txt_path = self._save_txt(session_id, lines)
        pdf_path = self._save_pdf(
            session_id, student_name, student_id, exam_code,
            risk_score, label, event_counts, bar_chart, timeline_chart,
            generated, duration_sec, screenshots or [],
            event_log or [], browser_log or [], contributors or []
        )
        return txt_path, pdf_path

    # ── Text report ───────────────────────────────────────────

    def _build_lines(self, student_name, student_id, exam_code, session_id,
                     minutes, seconds, event_counts, risk_score, label,
                     generated, contributors) -> list:
        sep  = "=" * 60
        sep2 = "-" * 60
        lines = [
            sep,
            "          ProctorAI — Exam Integrity Report",
            sep,
            f"  Generated  : {generated}",
            f"  Session ID : {session_id}",
            sep2,
            "  STUDENT INFORMATION",
            sep2,
            f"  Name       : {student_name}",
            f"  Student ID : {student_id}",
            f"  Exam Code  : {exam_code}",
            f"  Duration   : {minutes}m {seconds}s",
            sep2,
            "  DETECTED EVENTS",
            sep2,
        ]
        for et, count in event_counts.items():
            if count > 0:
                lines.append(f"  {et:<25} {count:>3} occurrence(s)")
        if not any(v > 0 for v in event_counts.values()):
            lines.append("  No suspicious events detected.")
        lines += [
            sep2,
            "  RISK ASSESSMENT",
            sep2,
            f"  Final Risk Score : {risk_score}",
            f"  Verdict          : {label}",
            sep2,
            "  RISK CONTRIBUTORS",
            sep2,
        ]
        for c in contributors:
            lines.append(
                f"  {c['event_type']:<25} ×{c['count']}  +{c['points']} pts"
            )
        lines += [
            sep2,
            "  DISCLAIMER",
            sep2,
            "  All flagged events require manual review by the examiner.",
            "  This system is an AI monitoring aid, not a final verdict.",
            "  Do not make academic decisions based solely on this report.",
            sep,
        ]
        return lines

    def _save_txt(self, session_id: str, lines: list) -> str:
        path = os.path.join(REPORTS_DIR, f"{session_id}_report.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info(f"TXT report → {path}")
        return path

    # ── PDF report ────────────────────────────────────────────

    def _save_pdf(
        self, session_id, student_name, student_id, exam_code,
        risk_score, label, event_counts, bar_chart, timeline_chart,
        generated, duration_sec, screenshots, event_log,
        browser_log, contributors
    ):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table,
                TableStyle, HRFlowable, Image as RLImage
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except ImportError:
            logger.warning("reportlab not installed — PDF skipped.")
            return None

        path = os.path.join(REPORTS_DIR, f"{session_id}_report.pdf")
        doc  = SimpleDocTemplate(
            path, pagesize=letter,
            leftMargin=0.65*inch, rightMargin=0.65*inch,
            topMargin=0.65*inch,  bottomMargin=0.65*inch
        )

        styles = getSampleStyleSheet()
        NAVY  = colors.HexColor("#1B2A4A")
        BLUE  = colors.HexColor("#2563EB")
        GREEN = colors.HexColor("#059669")
        AMBER = colors.HexColor("#B45309")
        RED   = colors.HexColor("#DC2626")
        LGRAY = colors.HexColor("#F1F5F9")
        DGRAY = colors.HexColor("#64748B")

        risk_color = (RED   if label in ("Suspicious", "Critical") else
                      AMBER if label == "Moderate" else GREEN)

        sT  = ParagraphStyle("T",  parent=styles["Title"],
                             textColor=NAVY, fontSize=22, spaceAfter=2)
        sSub = ParagraphStyle("Sub", parent=styles["Normal"],
                              textColor=DGRAY, fontSize=10, spaceAfter=10)
        sH2 = ParagraphStyle("H2", parent=styles["Heading2"],
                             textColor=BLUE, fontSize=13,
                             spaceBefore=14, spaceAfter=5)
        sB  = ParagraphStyle("B",  parent=styles["Normal"],
                             fontSize=9, leading=13)
        sW  = ParagraphStyle("W",  parent=styles["Normal"],
                             fontSize=8, textColor=DGRAY, leading=12)

        story = [
            Paragraph("ProctorAI", sT),
            Paragraph("Exam Integrity Report", sSub),
            HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=10),
        ]

        # Verdict banner
        verdict_bg = (
            colors.HexColor("#FEF2F2") if label in ("Suspicious","Critical") else
            colors.HexColor("#FFFBEB") if label == "Moderate" else
            colors.HexColor("#F0FDF4")
        )
        verdict_text = (
            "⚠ HIGH RISK — Manual review required. Do not act on this report alone."
            if label in ("Suspicious", "Critical") else
            "⚠ MODERATE RISK — Events flagged for examiner review."
            if label == "Moderate" else
            "✓ LOW RISK — Session within normal parameters."
        )
        vt = Table([[Paragraph(verdict_text, ParagraphStyle(
            "V", parent=styles["Normal"], fontSize=9,
            textColor=risk_color, leading=13
        ))]], colWidths=[6.7*inch])
        vt.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), verdict_bg),
            ("BOX",        (0,0),(-1,-1), 1.0, risk_color),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ]))
        story += [vt, Spacer(1, 0.12*inch)]

        # Student info
        mins = duration_sec // 60
        secs = duration_sec % 60
        info_data = [
            ["Student Name", student_name],
            ["Student ID",   student_id],
            ["Exam Code",    exam_code],
            ["Session ID",   session_id],
            ["Duration",     f"{mins}m {secs}s"],
            ["Generated",    generated],
            ["Final Score",  str(risk_score)],
            ["Verdict",      label],
        ]
        it = Table(info_data, colWidths=[1.8*inch, 4.9*inch])
        it.setStyle(TableStyle([
            ("FONT",  (0,0),(0,-1), "Helvetica-Bold", 9),
            ("FONT",  (1,0),(1,-1), "Helvetica", 9),
            ("TEXTCOLOR", (1,7),(1,7), risk_color),
            ("ROWBACKGROUNDS", (0,0),(-1,-1), [colors.white, LGRAY]),
            ("GRID", (0,0),(-1,-1), 0.4, colors.HexColor("#CBD5E1")),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ]))
        story += [Paragraph("Student Information", sH2), it, Spacer(1, 0.1*inch)]

        # Events table
        story.append(Paragraph("Detected Events", sH2))
        from core.risk.risk_config import BASE_POINTS
        ev_data = [["Event Type", "Count", "Risk Points", "Severity"]]
        for et, cnt in event_counts.items():
            pts = BASE_POINTS.get(et, 0) * cnt
            sev = "HIGH" if pts >= 20 else "MED" if pts >= 10 else "LOW" if cnt > 0 else "—"
            ev_data.append([et, str(cnt), f"+{pts}", sev])
        et2 = Table(ev_data, colWidths=[2.8*inch, 0.8*inch, 1.1*inch, 2.0*inch])
        et2.setStyle(TableStyle([
            ("FONT",       (0,0),(-1,0), "Helvetica-Bold", 9),
            ("BACKGROUND", (0,0),(-1,0), NAVY),
            ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, LGRAY]),
            ("GRID",  (0,0),(-1,-1), 0.4, colors.HexColor("#CBD5E1")),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ]))
        story += [et2, Spacer(1, 0.1*inch)]

        # Explainable risk contributors
        if contributors:
            story.append(Paragraph("Risk Score Explanation", sH2))
            contrib_data = [["Event Type", "Count", "Points", "% of Score"]]
            for c in contributors[:8]:
                contrib_data.append([
                    c["event_type"], str(c["count"]),
                    f"+{c['points']}", f"{c['pct']}%"
                ])
            ct = Table(contrib_data, colWidths=[2.8*inch, 0.8*inch, 1.0*inch, 2.1*inch])
            ct.setStyle(TableStyle([
                ("FONT",       (0,0),(-1,0), "Helvetica-Bold", 9),
                ("BACKGROUND", (0,0),(-1,0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
                ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, LGRAY]),
                ("GRID",  (0,0),(-1,-1), 0.4, colors.HexColor("#CBD5E1")),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ]))
            story += [ct, Spacer(1, 0.1*inch)]

        # Charts
        if bar_chart and os.path.exists(bar_chart):
            story += [Paragraph("Events Chart", sH2),
                      RLImage(bar_chart, width=5.5*inch, height=2.5*inch),
                      Spacer(1, 0.08*inch)]

        if timeline_chart and os.path.exists(timeline_chart):
            story += [Paragraph("Risk Score Timeline", sH2),
                      RLImage(timeline_chart, width=5.5*inch, height=2.2*inch),
                      Spacer(1, 0.08*inch)]

        # Evidence gallery
        if screenshots:
            story.append(Paragraph("Evidence Gallery", sH2))
            story.append(Paragraph(
                "Screenshots captured at suspicious event moments. "
                "Examine manually before drawing conclusions.",
                sW
            ))
            story.append(Spacer(1, 0.06*inch))
            row_data = []
            row_imgs  = []
            for idx, ev in enumerate(screenshots[:6]):
                if isinstance(ev, str):
                    ev = {"path": ev, "event_type": "screenshot", "time": "", "risk_score": 0}
                p = ev.get("path", "")
                if p and os.path.exists(p):
                    try:
                        img = RLImage(p, width=1.8*inch, height=1.35*inch)
                    except Exception:
                        img = Paragraph("(image error)", sW)
                else:
                    img = Paragraph("(missing)", sW)
                caption = Paragraph(
                    f"<b>{ev.get('event_type','')}</b><br/>"
                    f"{ev.get('time','')} | Score: {ev.get('risk_score',0)}",
                    ParagraphStyle("cap", parent=styles["Normal"],
                                   fontSize=7, leading=9, alignment=TA_CENTER)
                )
                row_imgs.append([img, caption])
                if len(row_imgs) == 3:
                    row_data.append([row_imgs[0], row_imgs[1], row_imgs[2]])
                    row_imgs = []
            if row_imgs:
                while len(row_imgs) < 3:
                    row_imgs.append(["", ""])
                row_data.append(row_imgs)

            for row in row_data:
                flat = [[row[0][0], row[1][0], row[2][0]],
                        [row[0][1], row[1][1], row[2][1]]]
                gt = Table(flat, colWidths=[2.2*inch]*3)
                gt.setStyle(TableStyle([
                    ("ALIGN",  (0,0),(-1,-1), "CENTER"),
                    ("VALIGN", (0,0),(-1,-1), "TOP"),
                    ("TOPPADDING",    (0,0),(-1,-1), 4),
                    ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ]))
                story += [gt, Spacer(1, 0.05*inch)]

        # Event timeline
        if event_log:
            story.append(Paragraph("Event Timeline", sH2))
            tl_data = [["Time", "Event Type", "Notes"]]
            for e in event_log[-30:]:
                tl_data.append([
                    _display_time(e.get("time") or e.get("event_time") or e.get("timestamp")),
                    e.get("event_type", ""),
                    str(e.get("notes") or e.get("count") or "")[:60],
                ])
            tl = Table(tl_data, colWidths=[0.9*inch, 3.8*inch, 2.0*inch])
            tl.setStyle(TableStyle([
                ("FONT",       (0,0),(-1,0), "Helvetica-Bold", 8),
                ("BACKGROUND", (0,0),(-1,0), NAVY),
                ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
                ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, LGRAY]),
                ("GRID",  (0,0),(-1,-1), 0.3, colors.HexColor("#CBD5E1")),
                ("FONTSIZE",   (0,1),(-1,-1), 8),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
                ("LEFTPADDING",   (0,0),(-1,-1), 5),
            ]))
            story += [tl, Spacer(1, 0.1*inch)]

        # Browser activity
        if browser_log:
            story.append(Paragraph("Browser Activity Timeline", sH2))
            bl_data = [["Time", "Event", "Description"]]
            for e in browser_log[:20]:
                bl_data.append([
                    e.get("time", ""),
                    e.get("event_type", "")[:25],
                    e.get("description", "")[:55],
                ])
            blt = Table(bl_data, colWidths=[0.8*inch, 2.0*inch, 3.9*inch])
            blt.setStyle(TableStyle([
                ("FONT",       (0,0),(-1,0), "Helvetica-Bold", 8),
                ("BACKGROUND", (0,0),(-1,0), NAVY),
                ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
                ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, LGRAY]),
                ("GRID",  (0,0),(-1,-1), 0.3, colors.HexColor("#CBD5E1")),
                ("FONTSIZE",   (0,1),(-1,-1), 8),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
                ("LEFTPADDING",   (0,0),(-1,-1), 5),
            ]))
            story += [blt, Spacer(1, 0.1*inch)]

        # Disclaimer
        story += [
            HRFlowable(width="100%", thickness=1,
                       color=colors.HexColor("#CBD5E1")),
            Spacer(1, 0.06*inch),
            Paragraph(
                "⚠ IMPORTANT: All flagged events require manual review by a "
                "qualified examiner. This AI report is a monitoring aid only. "
                "Do not make academic or disciplinary decisions based solely "
                "on this automated report. False positives are possible.",
                ParagraphStyle("disc", parent=styles["Normal"],
                               fontSize=7.5, textColor=DGRAY, leading=11)
            )
        ]

        doc.build(story)
        logger.info(f"PDF report → {path}")
        return path

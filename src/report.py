#!/usr/bin/env python3
from __future__ import annotations  # Python 3.8 compat for list[...] type hints
"""
report.py - Generate a monthly PDF security report from local log files.

Merges what were previously pdf_generator.py + monthly_report.py into one
clean module. Log aggregation happens fully in memory — no temp files written.

Usage:
    python3 report.py [config_file] [year] [month]
    python3 report.py /etc/security-updater/config.env 2026 2
"""

import glob
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import Config, load_config

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

SEP = "=" * 70


# ── Styles ───────────────────────────────────────────────────────────────────

def _make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "Title2",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=8,
        spaceBefore=14,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "Body2",
        parent=styles["BodyText"],
        fontSize=9,
        textColor=colors.HexColor("#333333"),
        spaceAfter=4,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "LogCode",
        parent=styles["Code"],
        fontSize=7.5,
        textColor=colors.HexColor("#222222"),
        fontName="Courier",
        spaceAfter=2,
        leading=11,
    ))
    return styles


# ── Log collection ────────────────────────────────────────────────────────────

def collect_logs(log_dir: str, year: int, month: int) -> list[tuple[str, str]]:
    """
    Return list of (filename, content) for every log file matching the month.
    No files are written — content lives in memory.
    """
    pattern = os.path.join(log_dir, f"security-update_{year}{month:02d}*.log")
    paths = sorted(glob.glob(pattern))
    log.info(f"Found {len(paths)} log(s) for {year}-{month:02d}")

    results = []
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                results.append((os.path.basename(path), fh.read()))
        except OSError as exc:
            log.warning(f"Could not read {path}: {exc}")
            results.append((os.path.basename(path), f"[ERROR reading file: {exc}]"))
    return results


# ── Log parsing ───────────────────────────────────────────────────────────────

def _parse_log(content: str) -> dict:
    """Extract structured info from a single log's text content."""
    data = {
        "started": "N/A",
        "finished": "N/A",
        "status": "Unknown",
        "packages": [],
        "errors": [],
    }

    m = re.search(r"Started\s*:\s*(.+)", content)
    if m:
        data["started"] = m.group(1).strip()

    m = re.search(r"Finished\s*:\s*(.+)", content)
    if m:
        data["finished"] = m.group(1).strip()

    m = re.search(r"Status\s*:\s*(.+)", content)
    if m:
        data["status"] = m.group(1).strip()

    # Packages: match lines like "  libssl3 (3.0.2-0ubuntu1.10 => 3.0.2-0ubuntu1.12)"
    pkg_re = re.compile(r"^\s+([\w.\-]+)\s+\(([\d.\w~+:-]+)\s+=>\s+([\d.\w~+:-]+)\)", re.M)
    data["packages"] = [
        {"name": m.group(1), "old": m.group(2), "new": m.group(3)}
        for m in pkg_re.finditer(content)
    ]

    # Errors: lines containing error/fail (case-insensitive), skipping apt progress lines
    error_lines = [
        ln.strip() for ln in content.splitlines()
        if re.search(r"\b(error|failed|fail)\b", ln, re.I)
        and not ln.strip().startswith("Get:")
        and ln.strip()
    ]
    data["errors"] = error_lines[:10]

    return data


# ── PDF builder ───────────────────────────────────────────────────────────────

def _status_color(status: str) -> colors.Color:
    s = status.upper()
    if "SUCCESS" in s:
        return colors.HexColor("#27ae60")
    if "ERROR" in s or "FAIL" in s:
        return colors.HexColor("#c0392b")
    return colors.HexColor("#e67e22")


def build_pdf(
    entries: list[tuple[str, str]],
    output_path: str,
    cfg: Config,
    year: int,
    month: int,
) -> str:
    """Build the monthly PDF entirely from in-memory log content."""

    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)
    styles = _make_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=54, leftMargin=54,
        topMargin=54, bottomMargin=36,
    )
    month_label = datetime(year, month, 1).strftime("%B %Y")
    elements = []

    # ── Title ────────────────────────────────────────────────────────────────
    elements.append(Paragraph(
        f"Monthly Security Report<br/>{cfg.server_name}",
        styles["Title2"],
    ))
    elements.append(Spacer(1, 0.1 * inch))

    # ── Top summary table ─────────────────────────────────────────────────────
    summary = [
        ["Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Period",           month_label],
        ["Environment",      cfg.environment.upper()],
        ["Server",           cfg.server_name],
        ["Total Updates",    str(len(entries))],
    ]
    t = Table(summary, colWidths=[1.8 * inch, 4.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",    (0, 0), (0, -1), colors.whitesmoke),
        ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",     (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.25 * inch))

    # ── Per-run sections ──────────────────────────────────────────────────────
    for idx, (filename, content) in enumerate(entries, 1):
        parsed = _parse_log(content)

        elements.append(Paragraph(
            f"Update #{idx} — {filename}",
            styles["Section"],
        ))

        # Status banner
        sc = _status_color(parsed["status"])
        sb = Table([[parsed["status"]]], colWidths=[6 * inch])
        sb.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), sc),
            ("TEXTCOLOR",    (0, 0), (-1, -1), colors.whitesmoke),
            ("FONTNAME",     (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 11),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",   (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ]))
        elements.append(sb)
        elements.append(Spacer(1, 0.1 * inch))

        # Timing row
        timing = [["Started", parsed["started"], "Finished", parsed["finished"]]]
        tt = Table(timing, colWidths=[0.9*inch, 2.1*inch, 0.9*inch, 2.1*inch])
        tt.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (0, 0), colors.HexColor("#34495e")),
            ("BACKGROUND",   (2, 0), (2, 0), colors.HexColor("#34495e")),
            ("TEXTCOLOR",    (0, 0), (0, 0), colors.whitesmoke),
            ("TEXTCOLOR",    (2, 0), (2, 0), colors.whitesmoke),
            ("FONTNAME",     (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
        ]))
        elements.append(tt)
        elements.append(Spacer(1, 0.1 * inch))

        # Packages updated table
        if parsed["packages"]:
            elements.append(Paragraph("Packages Updated", styles["Section"]))
            pkg_data = [["Package", "Old Version", "New Version"]]
            for p in parsed["packages"][:30]:
                pkg_data.append([p["name"], p["old"], p["new"]])
            pt = Table(pkg_data, colWidths=[2.5*inch, 1.75*inch, 1.75*inch])
            pt.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#3498db")),
                ("TEXTCOLOR",     (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",      (0, 0), (-1, -1), 8),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f0f3f4")]),
            ]))
            elements.append(pt)
            elements.append(Spacer(1, 0.1 * inch))

        # Errors section
        if parsed["errors"]:
            elements.append(Paragraph("Errors / Warnings", styles["Section"]))
            for err in parsed["errors"]:
                elements.append(Paragraph(f"• {err}", styles["Body2"]))
            elements.append(Spacer(1, 0.1 * inch))

        # Raw log (monospaced, truncated to 80 lines to keep PDF manageable)
        elements.append(Paragraph("Raw Log Output", styles["Section"]))
        lines = content.splitlines()[:80]
        for line in lines:
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(safe or "&nbsp;", styles["LogCode"]))
        if len(content.splitlines()) > 80:
            elements.append(Paragraph(
                f"<i>... {len(content.splitlines()) - 80} more lines truncated. See full log on disk.</i>",
                styles["Body2"],
            ))

        elements.append(Spacer(1, 0.3 * inch))

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "<i>Auto-generated by Security Update Automation System</i>",
        styles["Body2"],
    ))

    doc.build(elements)
    log.info(f"PDF saved: {output_path}")
    return output_path


# ── Telegram sender ───────────────────────────────────────────────────────────

def send_to_telegram(pdf_path: str, cfg: Config, year: int, month: int) -> bool:
    """
    Upload the PDF to the Telegram channel. Uses only stdlib (no extra deps).
    Returns True on success, False on failure.
    """
    if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        log.info("Telegram not configured — skipping notification")
        return False

    import urllib.request

    month_label = datetime(year, month, 1).strftime("%B %Y")
    caption = (
        f"🔒 *Security Update Report \u2014 {month_label}*\n\n"
        f"Server: {cfg.server_name}\n"
        f"Environment: {cfg.environment}\n\n"
        f"_Auto-generated by Security Update Automation System_"
    )

    boundary = "----TelegramFormBoundary7MA4YWxk"
    filename = os.path.basename(pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{cfg.telegram_chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
        f"Markdown\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_data + f"\r\n--{boundary}--\r\n".encode()

    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendDocument"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        import json
        result = json.loads(resp.read())
        if result.get("ok"):
            log.info(f"Telegram: PDF sent (message_id={result['result']['message_id']})")
            return True
        else:
            log.warning(f"Telegram API error: {result}")
            return False
    except Exception as exc:
        log.warning(f"Telegram send failed: {exc}")
        return False


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_monthly_report(
    config_file: str = "/etc/security-updater/config.env",
    year: int | None = None,
    month: int | None = None,
) -> str | None:
    cfg = load_config(config_file)

    now = datetime.now()
    year = year or now.year
    month = month or now.month

    entries = collect_logs(cfg.log_dir, year, month)
    if not entries:
        log.warning(f"No logs found for {year}-{month:02d}. Nothing to report.")
        return None

    month_label = f"{year}{month:02d}"
    filename = f"security_monthly_{month_label}_{cfg.server_name}.pdf"
    output_path = os.path.join(cfg.report_dir, filename)

    pdf_path = build_pdf(entries, output_path, cfg, year, month)
    send_to_telegram(pdf_path, cfg, year, month)
    return pdf_path


def main():
    args = sys.argv[1:]
    config_file = args[0] if args else "/etc/security-updater/config.env"
    year  = int(args[1]) if len(args) > 1 else None
    month = int(args[2]) if len(args) > 2 else None

    path = generate_monthly_report(config_file, year, month)
    if path:
        print(f"Report generated: {path}")
        sys.exit(0)
    else:
        print("No report generated — check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

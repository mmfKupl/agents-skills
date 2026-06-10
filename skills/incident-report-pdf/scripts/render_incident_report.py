#!/usr/bin/env python3

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"\[\[([a-zA-Z0-9_]+)\]\]")
REQUIRED_KEYS = {
    "doc_title",
    "report_title",
    "reporter_last_name",
    "reporter_first_name",
    "reporter_position",
    "reporter_company",
    "reporter_phone",
    "reporter_email",
    "organization_name",
    "organization_type",
    "street_address",
    "other_organizations",
    "incident_date",
    "incident_time",
    "affected_location",
    "brief_summary",
    "project_program",
    "classification_level",
    "system_compromise",
    "data_compromise",
    "originator_authority",
    "foreign_government",
    "accredited_system",
    "estimated_injury",
    "estimated_impact",
    "incident_duration",
    "systems_affected_count",
    "systems_affected_percentage",
    "action_taken",
    "supporting_documents",
    "multiple_occurrences",
    "incident_status",
    "reported_to_authorities",
    "mitigation_details",
    "mitigation_results",
    "additional_assistance",
    "malicious_code",
    "known_vulnerability",
    "disruption_of_service",
    "access_violation",
    "accident_or_error",
    "user_error_details",
    "additional_details",
    "apparent_origin_details",
    "network_zone",
    "system_type",
    "operating_system",
    "protocols_services",
    "application_version",
    "authorities_info",
    "root_cause_analysis",
}
CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("google-chrome-stable") or "",
    shutil.which("chromium") or "",
    shutil.which("chrome") or "",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the standard incident report HTML template and optionally export a PDF.",
    )
    parser.add_argument("--input", required=True, help="Path to the normalized JSON payload.")
    parser.add_argument("--output-html", required=True, help="Path to the rendered HTML output.")
    parser.add_argument("--output-pdf", help="Optional path to the rendered PDF output.")
    parser.add_argument(
        "--template",
        default=str(Path(__file__).resolve().parent.parent / "assets" / "incident-report-template.html"),
        help="Path to the HTML template asset.",
    )
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Input JSON must contain an object at the top level.")
    missing = sorted(REQUIRED_KEYS - set(data.keys()))
    if missing:
        raise ValueError(f"Missing required keys: {', '.join(missing)}")
    return data


def escape_text(value: object) -> str:
    return html.escape(str(value)).replace("\n", "<br/>")


def render_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        items = "".join(f"<li>{escape_text(item)}</li>" for item in value)
        return f"<ul>{items}</ul>" if items else ""
    return escape_text(value)


def render_template(template_text: str, payload: dict[str, object]) -> str:
    rendered_values = {key: render_value(value) for key, value in payload.items()}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in rendered_values:
            raise KeyError(f"Template placeholder '{key}' has no value.")
        return rendered_values[key]

    rendered = PLACEHOLDER_RE.sub(replace, template_text)
    leftovers = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if leftovers:
        raise ValueError(f"Unresolved placeholders remain: {', '.join(leftovers)}")
    return rendered


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "Chrome binary not found. Set CHROME_BIN or install Google Chrome/Chromium."
    )


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = find_chrome()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--allow-file-access-from-files",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    template_path = Path(args.template).expanduser().resolve()
    output_html_path = Path(args.output_html).expanduser().resolve()
    output_pdf_path = Path(args.output_pdf).expanduser().resolve() if args.output_pdf else None

    payload = load_payload(input_path)
    template_text = template_path.read_text()
    rendered_html = render_template(template_text, payload)

    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    output_html_path.write_text(rendered_html)

    if output_pdf_path is not None:
        render_pdf(output_html_path, output_pdf_path)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)

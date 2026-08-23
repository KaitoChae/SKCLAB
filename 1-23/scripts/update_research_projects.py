#!/usr/bin/env python3
"""Refresh the laboratory research-project list from Prof. Siti's official ITB page.

The website is static, so this updater is intended to run in GitHub Actions.
It only replaces the saved project catalogue when at least one credible project
entry is parsed. A temporary network or markup failure therefore cannot erase
the last successful dataset shown on the site.
"""
from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data/research_projects.json"
JS_PATH = ROOT / "data/research_projects.js"
SOURCE_URL = "https://metallurgy.itb.ac.id/staff-akademik-siti-khodijah/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
}
SECTION_RE = re.compile(
    r"\b(research\s+projects?|projects?|riset|penelitian|proyek)\b", re.I
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
PERIOD_RE = re.compile(
    r"\((?:(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+)?(?P<year>(?:19|20)\d{2})"
    r"\s*[–—-]\s*present\s*\)\s*$",
    re.I,
)
MONTH_NUMBERS = {
    name.lower(): index
    for index, name in enumerate(
        ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        start=1,
    )
}
HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
REJECT_RE = re.compile(
    r"^(research|riset|penelitian|project|projects|proyek|year|tahun|title|judul|"
    r"read more|selengkapnya|home|profil|profile)$",
    re.I,
)

SOURCE_TITLES = [
    "Biogeochemical characterization of bioleaching bacteria isolated from sulfide and laterite mineral ores for developing an environmentally friendly, economical biomining in Indonesia",
    "Biogeochemical characterization of Arsenic (As)-resistant bacteria isolated from acid minerals with extremely low pH for developing bioremediation",
    "Biogeochemical characterization of mercury (Hg)-resistant bacteria isolated from river sediments contaminated with mining wastes for developing bioremediation",
    "Biomineralogical characterization of iron-oxidizing bacteria, sulphate-reducing bacteria and biofilm-producing bacteria for microbiologically influenced corrosion (MIC) or biocorrosion",
    "Biogeochemical characterization of hexavalent chromium (Cr+6)-resistant bacteria isolated from Cr-polluted saline-sodic agricultural soils for developing bioremediation",
    "Characterization of polyethylene-degrading bacteria and fungi for plastics biodegradation",
    "Biohydrometallurgy of nickel laterite",
    "Biosurfactants-producung bacteria for biohydrometallurgy, biocorrosion, biodesulfurization and microbial enhanced oil recovery (MEOR)",
    "Bioflotation of sulfide and silicate minerals",
    "Biohydrometallurgy of copper minerals",
    "Biohydrometallurgy of sulfide-bearing carbonaceous refractory gold ores",
]
DISPLAY_TITLES = [
    "Biogeochemical characterization of bioleaching bacteria isolated from sulfide and laterite mineral ores to develop environmentally friendly and economical biomining in Indonesia",
    "Biogeochemical characterization of arsenic (As)-resistant bacteria isolated from extremely acidic minerals to develop bioremediation",
    "Biogeochemical characterization of mercury (Hg)-resistant bacteria isolated from river sediments contaminated by mining waste to develop bioremediation",
    "Biomineralogical characterization of iron-oxidizing, sulfate-reducing, and biofilm-producing bacteria for microbiologically influenced corrosion (MIC) or biocorrosion",
    "Biogeochemical characterization of hexavalent chromium [Cr(VI)]-resistant bacteria isolated from Cr-polluted saline-sodic agricultural soils to develop bioremediation",
    "Characterization of polyethylene-degrading bacteria and fungi for plastic biodegradation",
    "Biohydrometallurgy of nickel laterite",
    "Biosurfactant-producing bacteria for biohydrometallurgy, biocorrosion, biodesulfurization, and microbial enhanced oil recovery (MEOR)",
    "Bioflotation of sulfide and silicate minerals",
    "Biohydrometallurgy of copper minerals",
    "Biohydrometallurgy of sulfide-bearing carbonaceous refractory gold ores",
]
DEFAULT_STARTS = ["2009-10", "2009-10", "2009-10", "2010-03", "2009-10", "2011", "2009", "2011", "2015", "2014", "2014"]


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n|·–—-")


def project_from_text(value: str, *, href: str = "") -> dict | None:
    text = clean_text(value)
    if len(text) < 18 or len(text) > 1200 or REJECT_RE.match(text):
        return None
    period_match = PERIOD_RE.search(text)
    start = ""
    year = None
    title = text
    if period_match:
        year = int(period_match.group("year"))
        month = period_match.group("month")
        start = f"{year:04d}-{MONTH_NUMBERS[month.lower()]:02d}" if month else str(year)
        title = clean_text(text[: period_match.start()])
    title = re.sub(r"^(judul|title|topik|topic)\s*:\s*", "", title, flags=re.I)
    if len(title) < 14 or REJECT_RE.match(title):
        return None
    return {
        "start": start,
        "year": year,
        "title": title,
        "details": "",
        "url": href,
    }


def official_ordered_list_projects(root: Tag) -> list[dict]:
    """Read the numbered RESEARCH PROJECT list and stop before publications."""
    markers = root.find_all(
        lambda tag: isinstance(tag, Tag)
        and clean_text(tag.get_text(" ", strip=True)).upper() in {"RESEARCH PROJECT", "RESEARCH PROJECTS"}
    )
    for marker in markers:
        for node in marker.find_all_next():
            if root not in node.parents and node is not root:
                break
            text = clean_text(node.get_text(" ", strip=True))
            if text.upper().startswith("PUBLICATIONS AND CONFERENCES"):
                break
            if node.name not in {"ol", "ul"}:
                continue
            projects = [
                project
                for item in node.find_all("li", recursive=False)
                if (project := project_from_text(item.get_text(" ", strip=True)))
            ]
            if projects:
                return projects
    return []


def table_projects(table: Tag) -> list[dict]:
    projects: list[dict] = []
    for row in table.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        joined = " | ".join(cells)
        if REJECT_RE.match(clean_text(joined)) or all(REJECT_RE.match(cell) for cell in cells):
            continue
        year = next((YEAR_RE.search(cell).group(0) for cell in cells if YEAR_RE.search(cell)), None)
        title_candidates = [
            YEAR_RE.sub("", cell).strip(" |·–—-")
            for cell in cells
            if not REJECT_RE.match(cell) and not cell.isdigit()
        ]
        title_candidates = [cell for cell in title_candidates if len(cell) >= 14]
        if not title_candidates:
            continue
        title = max(title_candidates, key=len)
        details = " · ".join(cell for cell in cells if cell != title and not YEAR_RE.fullmatch(cell))
        projects.append(
            {
                "year": int(year) if year else None,
                "title": title,
                "details": details,
                "url": "",
            }
        )
    return projects


def section_projects(root: Tag) -> list[dict]:
    projects: list[dict] = []
    headings = [
        node
        for node in root.find_all(list(HEADING_TAGS))
        if SECTION_RE.search(clean_text(node.get_text(" ", strip=True)))
    ]
    for heading in headings:
        level = HEADING_TAGS[heading.name]
        for node in heading.find_all_next():
            if node is heading:
                continue
            if node.name in HEADING_TAGS and HEADING_TAGS[node.name] <= level:
                break
            if root not in node.parents and node is not root:
                break
            if node.name == "table":
                projects.extend(table_projects(node))
                continue
            if node.name not in {"li", "p", "h4", "h5", "h6"}:
                continue
            if node.find_parent("table") or node.find_parent("li"):
                continue
            href = ""
            link = node.find("a", href=True)
            if link:
                href = urljoin(SOURCE_URL, link.get("href", ""))
            project = project_from_text(node.get_text(" ", strip=True), href=href)
            if project:
                projects.append(project)
    return projects


def labelled_widget_projects(root: Tag) -> list[dict]:
    """Handle Elementor/accordion layouts that do not use semantic headings."""
    projects: list[dict] = []
    labels = root.find_all(
        lambda tag: isinstance(tag, Tag)
        and tag.name in {"div", "span", "strong", "button"}
        and SECTION_RE.search(clean_text(tag.get_text(" ", strip=True)) or "")
        and len(clean_text(tag.get_text(" ", strip=True))) < 80
    )
    for label in labels:
        container = label.parent
        for _ in range(3):
            if not container:
                break
            tables = container.find_all("table")
            lists = container.find_all(["ul", "ol"])
            if tables or lists:
                for table in tables:
                    projects.extend(table_projects(table))
                for item in container.find_all("li"):
                    project = project_from_text(item.get_text(" ", strip=True))
                    if project:
                        projects.append(project)
                break
            container = container.parent
    return projects


def dedupe(projects: list[dict]) -> list[dict]:
    output: list[dict] = []
    seen: set[str] = set()
    for project in projects:
        title = clean_text(project.get("title", ""))
        key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        if len(key) < 12 or key in seen:
            continue
        seen.add(key)
        project["title"] = title
        project["start"] = clean_text(project.get("start", ""))
        project["details"] = clean_text(project.get("details", ""))
        project["url"] = clean_text(project.get("url", ""))
        output.append(project)
    return output


def canonicalize(projects: list[dict]) -> list[dict]:
    source_index = {
        re.sub(r"[^a-z0-9]+", " ", title.lower()).strip(): index
        for index, title in enumerate(SOURCE_TITLES)
    }
    for project in projects:
        key = re.sub(r"[^a-z0-9]+", " ", project["title"].lower()).strip()
        index = source_index.get(key)
        if index is not None:
            project["id"] = f"official-{index + 1:02d}"
            project["title"] = DISPLAY_TITLES[index]
            project["start"] = project.get("start") or DEFAULT_STARTS[index]
            project["year"] = int(project["start"][:4])
        else:
            project["id"] = "official-new-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return projects


def fetch_projects() -> list[dict]:
    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=45)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    root = (
        soup.select_one("article .entry-content")
        or soup.select_one(".elementor-widget-theme-post-content")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.body
    )
    if root is None:
        raise RuntimeError("The official profile page returned no readable content")
    projects = official_ordered_list_projects(root)
    if not projects:
        projects = dedupe(section_projects(root) + labelled_widget_projects(root))
    projects = canonicalize(dedupe(projects))
    if not projects:
        raise RuntimeError("No research-project entries were found; keeping the last successful dataset")
    return projects


def save(projects: list[dict]) -> None:
    payload = {
        "source": "Official ITB staff profile",
        "source_url": SOURCE_URL,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "items": projects,
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JS_PATH.write_text(
        "window.LAB_RESEARCH_PROJECT_DATA="
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    projects = fetch_projects()
    save(projects)
    print(f"Saved {len(projects)} research projects from {SOURCE_URL}")


if __name__ == "__main__":
    main()

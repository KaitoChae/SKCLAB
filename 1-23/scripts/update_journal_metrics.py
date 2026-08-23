#!/usr/bin/env python3
"""Refresh journal quartiles, SJR values, and verified Impact Factors.

Quartile and SJR data come from the latest available SCImago CSV. Journal
Impact Factor values are only written when they are available from an official
publisher page or an optional licensed JCR JSON feed. Missing metrics are kept
explicitly unavailable; the script never guesses a value.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS_JSON = ROOT / "data/publications.json"
PUBLICATIONS_JS = ROOT / "data/publications.js"

SCIMAGO_URLS = (
    "https://www.scimagojr.com/journalrank.php?out=xls",
    "https://univ-nantes.io/bibliometrie/lppl-indicateurs/-/raw/main/scimagojr%202025.csv",
    "https://raw.githubusercontent.com/saramabrouk173/zotero-sjr-ranker/main/scimagojr%202024.csv",
)

JOURNAL_ALIASES = {
    "environmental nanotechnology monitoring and management": "environmental nanotechnology monitoring and management",
    "frontiers of materials science in china": "frontiers of materials science",
    "mineral processing and extractive metallurgy": "mineral processing and extractive metallurgy transactions of the institute of mining and metallurgy",
    "water air and soil pollution": "water air and soil pollution",
    "iop conference series materials science and engineering": "iop conference series materials science and engineering",
}

# Latest values publicly displayed by the journal publishers. The year denotes
# the publisher metric snapshot, not an article's publication year.
PUBLIC_JIF = {
    "atmospheric environment": (3.8, 2025, "Elsevier journal metrics"),
    "environment international": (10.2, 2025, "Elsevier journal metrics"),
    "hydrometallurgy": (6.3, 2025, "Elsevier journal metrics"),
    "minerals engineering": (6.0, 2025, "Elsevier journal metrics"),
    "international journal of coal geology": (7.3, 2025, "Elsevier journal metrics"),
    "international journal of hydrogen energy": (9.2, 2025, "Elsevier journal metrics"),
    "journal of sustainable metallurgy": (3.5, 2025, "Springer Nature journal metrics"),
    "scientific reports": (4.9, 2025, "Nature Portfolio journal metrics"),
    "frontiers in microbiology": (5.8, 2025, "Frontiers journal metrics"),
    "journal of applied polymer science": (3.1, 2025, "Wiley journal metrics"),
    "environmental chemistry letters": (25.2, 2025, "Springer Nature journal metrics"),
    "mineral processing and extractive metallurgy review": (4.7, 2025, "Taylor & Francis journal metrics"),
}


def norm(value: str) -> str:
    value = str(value or "").lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def metric_year(fieldnames: list[str] | None) -> int | None:
    for field in fieldnames or []:
        match = re.search(r"\((20\d{2})\)", field)
        if match:
            return int(match.group(1))
    return None


def parse_decimal(value: str):
    try:
        return float(str(value).strip().replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def read_scimago_csv(raw: str, source: str):
    reader = csv.DictReader(io.StringIO(raw.lstrip("\ufeff")), delimiter=";")
    year = metric_year(reader.fieldnames)
    rows = {}
    for row in reader:
        title = norm(row.get("Title", ""))
        if not title:
            continue
        rows[title] = {
            "sjr": parse_decimal(row.get("SJR", "")),
            "quartile": str(row.get("SJR Best Quartile", "") or "").strip(),
            "year": year,
            "source": f"SCImago Journal Rank {year or ''}".strip(),
            "source_url": source,
        }
    if not rows:
        raise RuntimeError("SCImago CSV contained no journal rows")
    return rows, year


def load_scimago():
    local_paths = os.getenv("SCIMAGO_CSV_PATHS", "").strip() or os.getenv("SCIMAGO_CSV_PATH", "").strip()
    if local_paths:
        datasets = []
        for raw_path in local_paths.split(os.pathsep):
            path = Path(raw_path)
            datasets.append(read_scimago_csv(path.read_text(encoding="utf-8-sig"), str(path)))
        return sorted(datasets, key=lambda item: item[1] or 0, reverse=True)

    custom_url = os.getenv("SCIMAGO_CSV_URL", "").strip()
    import requests
    urls = (custom_url,) if custom_url else SCIMAGO_URLS
    datasets = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BiominingLabMetrics/1.0)"}
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=75)
            response.raise_for_status()
            parsed = read_scimago_csv(response.content.decode("utf-8-sig"), url)
            if not any(year == parsed[1] for _, year in datasets):
                datasets.append(parsed)
        except Exception as exc:
            print(f"SCImago source unavailable ({url}): {exc}")
    if not datasets:
        raise RuntimeError("No SCImago dataset could be loaded")
    return sorted(datasets, key=lambda item: item[1] or 0, reverse=True)


def journal_candidates(journal: str):
    raw = str(journal or "")
    candidates = [norm(raw)]
    candidates.extend(norm(part) for part in raw.split("/") if part.strip())
    alias = JOURNAL_ALIASES.get(norm(raw))
    if alias:
        candidates.insert(0, norm(alias))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def scimago_metric(journal: str, datasets):
    for rows, _year in datasets:
        for candidate in journal_candidates(journal):
            if candidate in rows:
                return rows[candidate]
    return None


def licensed_jif():
    url = os.getenv("JCR_JSON_URL", "").strip()
    if not url:
        return {}
    import requests
    response = requests.get(url, timeout=45)
    response.raise_for_status()
    raw = response.json()
    return {norm(name): metric for name, metric in raw.items()}


def unavailable_if_reason(pub):
    kind = norm(pub.get("type", ""))
    journal = norm(pub.get("journal", ""))
    if not journal:
        return "Journal not listed; no verified JIF available"
    if "conference" in kind or "proceedings" in journal:
        return "Conference or proceedings title; no Journal Impact Factor"
    return "No current publisher-verified Journal Impact Factor available"


def main():
    data = json.loads(PUBLICATIONS_JSON.read_text(encoding="utf-8"))
    datasets = load_scimago()
    licensed = licensed_jif()
    matched_sjr = matched_jif = 0

    for pub in data.get("publications", []):
        if pub.get("citations") is not None and not pub.get("citations_source"):
            pub["citations_source"] = pub.get("source") or "OpenAlex / Google Scholar snapshot"
        metric = scimago_metric(pub.get("journal", ""), datasets)
        if metric:
            pub["sjr"] = metric.get("sjr")
            pub["sjr_year"] = metric.get("year")
            pub["sjr_source"] = metric.get("source")
            pub["quartile"] = metric.get("quartile") or ""
            pub["quartile_year"] = metric.get("year")
            pub["quartile_source"] = metric.get("source")
            matched_sjr += 1
        else:
            pub["sjr"] = None
            pub["sjr_year"] = None
            pub["sjr_source"] = "Not listed in the latest SCImago dataset"
            pub["quartile"] = ""
            pub["quartile_year"] = None
            pub["quartile_source"] = "Not listed in the latest SCImago dataset"

        key = norm(pub.get("journal", ""))
        jif = licensed.get(key)
        if jif:
            pub["impact_factor"] = jif.get("impact_factor")
            pub["impact_factor_year"] = jif.get("year")
            pub["impact_factor_source"] = jif.get("source", "Clarivate JCR licensed feed")
            matched_jif += 1
        elif key in PUBLIC_JIF:
            value, year, source = PUBLIC_JIF[key]
            pub["impact_factor"] = value
            pub["impact_factor_year"] = year
            pub["impact_factor_source"] = source
            matched_jif += 1
        else:
            pub["impact_factor"] = None
            pub["impact_factor_year"] = None
            pub["impact_factor_source"] = unavailable_if_reason(pub)

    data["journal_metrics"] = {
        "sjr_source": "SCImago Journal Rank",
        "sjr_latest_year": max((year or 0 for _, year in datasets), default=None),
        "sjr_matches": matched_sjr,
        "impact_factor_policy": "Publisher-verified values or licensed JCR feed; unavailable values are not estimated",
        "impact_factor_matches": matched_jif,
    }
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    PUBLICATIONS_JSON.write_text(payload + "\n", encoding="utf-8")
    PUBLICATIONS_JS.write_text("window.LAB_PUBLICATION_DATA = " + payload + ";\n", encoding="utf-8")
    print(f"Journal metric update complete: SJR/Q {matched_sjr}, verified IF {matched_jif}")


if __name__ == "__main__":
    main()

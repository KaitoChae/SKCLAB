#!/usr/bin/env python3
"""Refresh the publication catalogue for the Biomining & Biometallurgy Lab site.

Goals
-----
* Keep a large local publication index so the website search can search the whole
  cached catalogue, even though only the latest publications are shown initially.
* Prefer Google Scholar data when it is accessible.
* Fall back to public scholarly profiles/registries when Google Scholar blocks an
  automated request, so the site does not collapse to only the newest SINTA items.
* Translate newly discovered publication titles and cache those translations in
  publications.json / publications.js.
* Preserve verified quartile/JIF metadata and publisher-provided publication
  visuals from earlier runs.

Source priority
---------------
1. Google Scholar via SerpApi (optional SERPAPI_KEY; full pagination)
2. Direct Google Scholar profile request (best effort; Google may return 403)
3. SINTA Google-Scholar mirror (usually newest items + Scholar metrics)
4. ResearchGate public publication profile (broad catalogue fallback)
5. Crossref records carrying the author's ORCID (metadata fallback)

Translation priority
--------------------
1. DeepL API (optional DEEPL_API_KEY)
2. deep-translator / Google Translate fallback

The official journal title is deliberately NOT translated. It is a bibliographic
proper name. The publication TITLE is translated and the original title is kept
for citation accuracy.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

try:
    from deep_translator import GoogleTranslator
except Exception:  # optional fallback
    GoogleTranslator = None

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data/publications.json"
JS_PATH = ROOT / "data/publications.js"
IMG_DIR = ROOT / "assets/publications"

SINTA_GS = "https://sinta.kemdiktisaintek.go.id/authors/profile/6033650/?view=googlescholar"
SINTA_SCOPUS = "https://sinta.kemdiktisaintek.go.id/authors/profile/6033650"
SCHOLAR_PROFILE = "https://scholar.google.com/citations"
RESEARCHGATE_PROFILE = "https://www.researchgate.net/profile/Siti-Chaerun"
CROSSREF_WORKS = "https://api.crossref.org/works"
OPENALEX_WORKS = "https://api.openalex.org/works"
PROFILE_ID = "qcCkFUwAAAAJ"
ORCID_ID = "0000-0002-4137-6253"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
SESSION = requests.Session()
SESSION.headers.update(UA)

TARGET_LANGS = [
    "id", "ja", "zh-CN", "zh-TW", "ko", "de", "tr",
    "fr", "es", "it", "pt", "nl", "sv",
]
GOOGLE_LANG = {
    "id": "id", "ja": "ja", "zh-CN": "zh-CN", "zh-TW": "zh-TW",
    "ko": "ko", "de": "de", "tr": "tr", "fr": "fr", "es": "es",
    "it": "it", "pt": "pt", "nl": "nl", "sv": "sv",
}
DEEPL_LANG = {
    "id": "ID", "ja": "JA", "zh-CN": "ZH-HANS", "zh-TW": "ZH-HANT",
    "ko": "KO", "de": "DE", "tr": "TR", "fr": "FR", "es": "ES",
    "it": "IT", "pt": "PT-BR", "nl": "NL", "sv": "SV",
}


def load_old() -> dict:
    try:
        return json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"metrics": {}, "publications": []}


def clean_title(s: str) -> str:
    """Website title rule: never display/store a sentence-ending full stop."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return re.sub(r"[\.。．]+\s*$", "", s).strip()


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_title(s).lower()).strip()


def safe_int(v, default=None):
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:
        return default


def blank_pub(**kwargs):
    base = dict(
        year=None,
        title="",
        title_translations={},
        authors="",
        journal="",
        details="",
        quartile="",
        quartile_year=None,
        quartile_source="",
        sjr=None,
        sjr_year=None,
        sjr_source="",
        impact_factor=None,
        impact_factor_year=None,
        impact_factor_source="",
        citations=None,
        citations_source="",
        url="",
        type="Journal",
        doi="",
        graphical_abstract="",
        graphical_abstract_kind="",
        source="",
    )
    base.update(kwargs)
    base["title"] = clean_title(base.get("title", ""))
    return base


def parse_year_cites(text: str):
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    year = int(years[-1]) if years else None
    m = re.search(r"([\d,]+)\s+cited", text, re.I)
    return year, safe_int(m.group(1), 0) if m else 0


def parse_sinta_metrics(soup: BeautifulSoup, old_metrics: dict) -> dict:
    """Update the four Scholar summary numbers when the public SINTA page exposes them."""
    metrics = dict(old_metrics or {})
    text = " ".join(soup.stripped_strings)
    # The public page contains a Summary table: Article Scopus GScholar, etc.
    patterns = {
        "publications": r"Article\s+[\d,.]+\s+([\d,.]+)",
        "citations": r"Citation\s+[\d,.]+\s+([\d,.]+)",
        "h_index": r"H-Index\s+[\d,.]+\s+([\d,.]+)",
        "i10_index": r"i10-Index\s+[\d,.]+\s+([\d,.]+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, re.I)
        if m:
            v = safe_int(m.group(1))
            if v is not None:
                metrics[key] = v
    return metrics


def parse_sinta_google_scholar(old_metrics=None):
    r = SESSION.get(SINTA_GS, timeout=35)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = clean_title(" ".join(a.stripped_strings))
        if "scholar.google.com" not in href or len(title) < 12:
            continue
        box = a
        for _ in range(6):
            if box.parent:
                box = box.parent
            txt = " ".join(box.stripped_strings)
            if re.search(r"\b20\d{2}\b", txt) and ("cited" in txt.lower() or len(txt) > 80):
                break
        text = " ".join(box.stripped_strings)
        year, cites = parse_year_cites(text)
        authors = ""
        ma = re.search(r"Authors\s*:\s*(.*?)(?=(?:19|20)\d{2}|[\d,]+\s+cited|$)", text, re.I)
        if ma:
            authors = ma.group(1).strip(" ·|")
        cleaned = text.replace(title, " ")
        cleaned = re.sub(r"Authors\s*:\s*.*?(?=(?:19|20)\d{2}|[\d,]+\s+cited|$)", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:19|20)\d{2}\b", " ", cleaned)
        cleaned = re.sub(r"\b[\d,]+\s+cited\b", " ", cleaned, flags=re.I)
        details = re.sub(r"\s+", " ", cleaned).strip(" ·|")[:280]
        journal = ""
        if details:
            journal = re.split(r"\d{1,4}\s*\(|\d{1,4}\s*,|,\s*\d{4}\b", details)[0].strip(" ,;")
        results.append(blank_pub(
            year=year, title=title, authors=authors, journal=journal, details=details,
            citations=cites, url=href, source="SINTA Google Scholar mirror"
        ))
    results = dedupe(results)
    if not results:
        raise RuntimeError("No SINTA Google Scholar publications parsed")
    return results, parse_sinta_metrics(soup, old_metrics or {})


def parse_sinta_scopus_quartiles():
    r = SESSION.get(SINTA_SCOPUS, timeout=35)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    mapping = {}
    for a in soup.find_all("a", href=True):
        title = clean_title(" ".join(a.stripped_strings))
        if len(title) < 15:
            continue
        node = a
        for _ in range(6):
            if node.parent:
                node = node.parent
            text = " ".join(node.stripped_strings)
            mq = re.search(r"\b(Q[1-4])\s+as\s+(Journal|Conference)", text, re.I)
            if mq:
                mapping[norm(title)] = (
                    mq.group(1).upper(),
                    "Conference Proceeding" if mq.group(2).lower().startswith("conference") else "Journal",
                )
                break
    return mapping


def serpapi_publications(key: str):
    """Fetch every Scholar-author page, not only the first 100 results."""
    articles = []
    for start in range(0, 1000, 100):
        params = {
            "engine": "google_scholar_author",
            "author_id": PROFILE_ID,
            "hl": "en",
            "num": "100",
            "start": str(start),
            "sort": "pubdate",
            "api_key": key,
        }
        r = SESSION.get("https://serpapi.com/search.json", params=params, timeout=55)
        r.raise_for_status()
        payload = r.json()
        page = payload.get("articles", []) or []
        if not page:
            break
        for x in page:
            title = clean_title(x.get("title", ""))
            if not title:
                continue
            year = safe_int(x.get("year"))
            publication = x.get("publication", "") or ""
            articles.append(blank_pub(
                year=year,
                title=title,
                authors=x.get("authors", "") or "",
                journal=publication,
                details=publication,
                citations=safe_int((x.get("cited_by") or {}).get("value"), 0),
                url=x.get("link") or f"https://scholar.google.com/scholar?q={quote_plus(title)}",
                source="Google Scholar via SerpApi",
            ))
        if len(page) < 100:
            break
    articles = dedupe(articles)
    if not articles:
        raise RuntimeError("SerpApi returned no articles")
    return articles


def direct_scholar_publications():
    """Best-effort direct profile read. Google may block GitHub Actions with 403."""
    out = []
    seen = set()
    for start in range(0, 500, 100):
        params = {
            "user": PROFILE_ID,
            "hl": "en",
            "pagesize": "100",
            "cstart": str(start),
            "view_op": "list_works",
            "sortby": "pubdate",
        }
        r = SESSION.get(SCHOLAR_PROFILE, params=params, timeout=40)
        if r.status_code in (403, 429):
            raise RuntimeError(f"Google Scholar blocked direct request ({r.status_code})")
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("tr.gsc_a_tr")
        if not rows:
            break
        added = 0
        for row in rows:
            a = row.select_one("a.gsc_a_at")
            if not a:
                continue
            title = clean_title(a.get_text(" ", strip=True))
            k = norm(title)
            if not k or k in seen:
                continue
            seen.add(k)
            grays = row.select("div.gs_gray")
            authors = grays[0].get_text(" ", strip=True) if grays else ""
            details = grays[1].get_text(" ", strip=True) if len(grays) > 1 else ""
            journal = re.split(r",\s*\d{4}\b|\d+\s*\(|,\s*\d+", details)[0].strip(" ,;")
            y = row.select_one("span.gsc_a_h") or row.select_one("td.gsc_a_y span")
            year = safe_int(y.get_text(strip=True)) if y else None
            c = row.select_one("td.gsc_a_c a")
            citations = safe_int(c.get_text(strip=True), 0) if c else 0
            href = urljoin("https://scholar.google.com", a.get("href", ""))
            out.append(blank_pub(
                year=year, title=title, authors=authors, journal=journal, details=details,
                citations=citations, url=href, source="Google Scholar direct profile"
            ))
            added += 1
        if added == 0 or len(rows) < 100:
            break
        time.sleep(0.7)
    if not out:
        raise RuntimeError("No direct Google Scholar publications parsed")
    return out


def researchgate_publications():
    """Broad public-profile fallback; useful when Scholar blocks automated access."""
    r = SESSION.get(RESEARCHGATE_PROFILE, timeout=45)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = clean_title(" ".join(a.stripped_strings))
        if "/publication/" not in href or len(title) < 15:
            continue
        if title.lower() in {"view", "download", "read more", "full-text available"}:
            continue
        node = a
        for _ in range(5):
            if node.parent:
                node = node.parent
            txt = " ".join(node.stripped_strings)
            if re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d{2}\b", txt, re.I):
                break
        txt = " ".join(node.stripped_strings)
        ym = re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(19\d{2}|20\d{2})\b", txt, re.I)
        year = int(ym.group(1)) if ym else (safe_int(re.search(r"\b(19\d{2}|20\d{2})\b", txt).group(1)) if re.search(r"\b(19\d{2}|20\d{2})\b", txt) else None)
        kind = "Conference Proceeding" if "conference paper" in txt.lower() else ("Book Chapter" if "chapter" in txt.lower() else "Journal")
        out.append(blank_pub(
            year=year,
            title=title,
            url=urljoin("https://www.researchgate.net", href),
            type=kind,
            source="ResearchGate public profile",
        ))
    out = dedupe(out)
    if not out:
        raise RuntimeError("No ResearchGate publications parsed")
    return out


def crossref_orcid_publications():
    params = {
        "filter": f"orcid:{ORCID_ID}",
        "rows": "1000",
        "select": "DOI,title,author,published,container-title,URL,type",
    }
    headers = dict(UA)
    headers["User-Agent"] += " biomining-lab-publication-updater/1.0 (mailto:skchaerun@itb.ac.id)"
    r = SESSION.get(CROSSREF_WORKS, params=params, timeout=50, headers=headers)
    r.raise_for_status()
    out = []
    for item in (r.json().get("message") or {}).get("items", []):
        title = clean_title(" ".join(item.get("title") or []))
        if not title:
            continue
        year = None
        for field in ("published-print", "published-online", "published"):
            parts = ((item.get(field) or {}).get("date-parts") or [])
            if parts and parts[0]:
                year = safe_int(parts[0][0])
                if year:
                    break
        authors = []
        for person in item.get("author") or []:
            name = " ".join(x for x in [person.get("given", ""), person.get("family", "")] if x).strip()
            if name:
                authors.append(name)
        journal = " ".join(item.get("container-title") or [])
        ctype = item.get("type", "")
        kind = "Conference Proceeding" if "proceedings" in ctype else ("Book Chapter" if "chapter" in ctype else "Journal")
        doi = item.get("DOI", "") or ""
        out.append(blank_pub(
            year=year, title=title, authors=", ".join(authors), journal=journal, details=journal,
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else ""), type=kind, doi=doi,
            source="Crossref ORCID metadata",
        ))
    out = dedupe(out)
    if not out:
        raise RuntimeError("No Crossref ORCID publications parsed")
    return out


def openalex_orcid_publications():
    """Broad ORCID-linked catalogue used when Scholar is unavailable or incomplete."""
    params = {
        "filter": f"author.orcid:{ORCID_ID}",
        "per-page": "200",
        "select": "id,doi,title,publication_year,authorships,primary_location,cited_by_count,type,open_access,best_oa_location",
    }
    r = SESSION.get(OPENALEX_WORKS, params=params, timeout=55)
    r.raise_for_status()
    out = []
    for item in r.json().get("results", []):
        title = clean_title(item.get("title", ""))
        if not title:
            continue
        authors = []
        for authorship in item.get("authorships") or []:
            name = ((authorship.get("author") or {}).get("display_name") or "").strip()
            if name:
                authors.append(name)
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        doi_url = item.get("doi") or ""
        doi = doi_url.rsplit("/", 1)[-1] if doi_url else ""
        url = doi_url or location.get("landing_page_url") or item.get("id") or ""
        work_type = str(item.get("type") or "").replace("-", " ").title()
        kind = "Conference Proceeding" if "Proceedings" in work_type else (work_type or "Journal")
        out.append(blank_pub(
            year=safe_int(item.get("publication_year")),
            title=title,
            authors=", ".join(authors),
            journal=source.get("display_name") or "",
            details=source.get("display_name") or "",
            citations=safe_int(item.get("cited_by_count"), 0),
            url=url,
            type=kind,
            doi=doi,
            source="OpenAlex via ORCID",
        ))
    out = dedupe(out)
    if not out:
        raise RuntimeError("No OpenAlex ORCID publications parsed")
    return out


def dedupe(pubs):
    out, seen = [], set()
    for p in pubs:
        p["title"] = clean_title(p.get("title", ""))
        k = norm(p["title"])
        if k and k not in seen:
            seen.add(k)
            out.append(p)
    return out


def merge_catalogue(source_sets, old):
    """Merge broad sources while keeping metadata from the most authoritative source."""
    oldmap = {norm(p.get("title", "")): p for p in old.get("publications", []) if norm(p.get("title", ""))}
    merged = {}

    # Older cache first so verified visuals, JIF and translations survive.
    for k, p in oldmap.items():
        merged[k] = blank_pub(**p)

    rank = {
        "Crossref ORCID metadata": 30,
        "OpenAlex via ORCID": 70,
        "ResearchGate public profile": 40,
        "SINTA Google Scholar mirror": 80,
        "Google Scholar direct profile": 95,
        "Google Scholar via SerpApi": 100,
    }
    current_rank = {k: 10 for k in merged}

    for source_name, pubs in source_sets:
        srank = rank.get(source_name, 20)
        for incoming in pubs:
            k = norm(incoming.get("title", ""))
            if not k:
                continue
            if k not in merged:
                merged[k] = blank_pub(**incoming)
                current_rank[k] = srank
                continue
            dest = merged[k]
            # Always fill missing metadata from any source.
            for f in ("year", "authors", "journal", "details", "url", "type", "doi"):
                if not dest.get(f) and incoming.get(f):
                    dest[f] = incoming.get(f)
            # Scholar/SINTA values should win for year/citation/link/details when present.
            if srank >= current_rank.get(k, 0):
                for f in ("year", "authors", "journal", "details", "url", "type"):
                    if incoming.get(f) not in (None, ""):
                        dest[f] = incoming.get(f)
                if incoming.get("citations") is not None:
                    dest["citations"] = incoming.get("citations")
                    dest["citations_source"] = incoming.get("source") or source_name
                dest["source"] = incoming.get("source") or source_name
                current_rank[k] = srank
            if incoming.get("doi") and not dest.get("doi"):
                dest["doi"] = incoming["doi"]
    return list(merged.values())


def apply_quartiles_and_old_metadata(pubs, old, qmap):
    oldmap = {norm(p.get("title", "")): p for p in old.get("publications", [])}
    for p in pubs:
        k = norm(p.get("title", ""))
        prev = oldmap.get(k, {})
        if k in qmap:
            p["quartile"], p["type"] = qmap[k]
        elif prev.get("quartile"):
            p["quartile"] = prev.get("quartile", "")
        for f in (
            "quartile_year", "quartile_source", "sjr", "sjr_year", "sjr_source",
            "impact_factor", "impact_factor_year", "impact_factor_source", "citations_source",
            "graphical_abstract", "graphical_abstract_kind", "title_translations",
        ):
            if prev.get(f) not in (None, "", {}):
                p[f] = prev.get(f)
        p["title"] = clean_title(p.get("title", ""))
        p["title_translations"] = {
            lang: clean_title(txt)
            for lang, txt in (p.get("title_translations") or {}).items()
            if txt
        }
    return pubs


def deepl_translate_batch(texts, lang, key):
    endpoint = "https://api-free.deepl.com/v2/translate" if key.endswith(":fx") else "https://api.deepl.com/v2/translate"
    translated = []
    for i in range(0, len(texts), 35):
        batch = texts[i:i+35]
        payload = [("text", x) for x in batch]
        payload += [("target_lang", DEEPL_LANG[lang]), ("preserve_formatting", "1")]
        r = SESSION.post(endpoint, data=payload, headers={"Authorization": f"DeepL-Auth-Key {key}"}, timeout=60)
        r.raise_for_status()
        translated.extend(x.get("text", "") for x in r.json().get("translations", []))
    return translated


def google_translate_batch(texts, lang):
    if GoogleTranslator is None:
        raise RuntimeError("deep-translator is unavailable")
    outputs = []
    for i in range(0, len(texts), 30):
        tr = GoogleTranslator(source="auto", target=GOOGLE_LANG[lang])
        outputs.extend(tr.translate_batch(texts[i:i+30]))
        time.sleep(0.15)
    return outputs


def refresh_title_translations(pubs):
    """Translate only missing title-language pairs; cached translations are preserved."""
    deepl_key = os.getenv("DEEPL_API_KEY", "").strip()
    # Work language-by-language so one failed language never blocks the others.
    for lang in TARGET_LANGS:
        missing = [p for p in pubs if p.get("title") and not (p.get("title_translations") or {}).get(lang)]
        if not missing:
            continue
        texts = [p["title"] for p in missing]
        outputs = None
        try:
            if deepl_key:
                outputs = deepl_translate_batch(texts, lang, deepl_key)
                provider = "DeepL"
            else:
                outputs = google_translate_batch(texts, lang)
                provider = "Google Translate fallback"
            if len(outputs) != len(missing):
                raise RuntimeError(f"translation count mismatch {len(outputs)} != {len(missing)}")
            for pub, translated in zip(missing, outputs):
                translated = clean_title(translated)
                if translated:
                    pub.setdefault("title_translations", {})[lang] = translated
            print(f"Translated {len(missing)} titles to {lang} via {provider}")
            time.sleep(0.25)
        except Exception as e:
            print(f"Title translation failed for {lang}: {e}")
    return pubs


def crossref_doi(title):
    try:
        r = SESSION.get(
            CROSSREF_WORKS,
            params={"query.title": title, "rows": 4, "select": "DOI,title,URL"},
            timeout=25,
        )
        r.raise_for_status()
        best = (0, None)
        for item in r.json().get("message", {}).get("items", []):
            cand = " ".join(item.get("title") or [])
            score = SequenceMatcher(None, norm(title), norm(cand)).ratio()
            if score > best[0]:
                best = (score, item.get("DOI"))
        return best[1] if best[0] >= .72 else ""
    except Exception as e:
        print("Crossref DOI lookup failed:", title[:55], e)
        return ""


def image_ok(url):
    try:
        r = SESSION.get(url, timeout=22, stream=True, allow_redirects=True)
        ctype = r.headers.get("content-type", "").lower()
        ok = r.status_code == 200 and ctype.startswith("image/")
        r.close()
        return ok
    except Exception:
        return False


def _img_src(img, base):
    if not img:
        return ""
    for attr in ("data-original", "data-src", "data-lazy-src", "data-hi-res-src", "src"):
        val = img.get(attr)
        if val and not str(val).startswith("data:"):
            return urljoin(base, str(val).strip())
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        bits = [x.strip().split()[0] for x in str(srcset).split(",") if x.strip()]
        if bits:
            return urljoin(base, bits[-1])
    return ""


def _html_image_candidates(html, base):
    patterns = [
        r'https?://[^"\'<>\s]+(?:graphical[-_]?abstract|visual[-_]?abstract)[^"\'<>\s]*',
        r'https?://[^"\'<>\s]+(?:ga1(?:_lrg)?\.(?:jpg|jpeg|png|webp))[^"\'<>\s]*',
        r'https?://[^"\'<>\s]+(?:toc|graphical)[^"\'<>\s]*\.(?:jpg|jpeg|png|webp)',
    ]
    out = []
    for pat in patterns:
        for hit in re.findall(pat, html, flags=re.I):
            u = urljoin(base, hit.replace("\\u002F", "/").replace("\\/", "/"))
            if u not in out:
                out.append(u)
    return out


def discover_publisher_visual(doi):
    if not doi:
        return "", ""
    try:
        r = SESSION.get("https://doi.org/" + doi, timeout=30, allow_redirects=True)
        r.raise_for_status()
        final, html = r.url, r.text
    except Exception as e:
        print("DOI landing page failed:", doi, e)
        return "", ""
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        hint = " ".join([
            img.get("alt", ""), img.get("title", ""),
            img.get("class") and " ".join(img.get("class")) or "",
        ]).lower()
        if "graphical abstract" in hint or "visual abstract" in hint or "graphical-abstract" in hint:
            u = _img_src(img, final)
            if u and image_ok(u):
                return u, "graphical_abstract"
    for fig in soup.find_all(["figure", "div"]):
        txt = " ".join(fig.stripped_strings).lower()[:350]
        if "graphical abstract" in txt or "visual abstract" in txt:
            img = fig.find("img")
            if img:
                u = _img_src(img, final)
                if u and image_ok(u):
                    return u, "graphical_abstract"
    for u in _html_image_candidates(html, final):
        if image_ok(u):
            return u, "graphical_abstract"
    m = re.search(r"/pii/(S[0-9X]+)", final, re.I) or re.search(r'"pii"\s*:\s*"(S[0-9X]+)"', html, re.I)
    if m:
        pii = m.group(1)
        for suffix in ("ga1_lrg.jpg", "ga1.jpg"):
            u = f"https://ars.els-cdn.com/content/image/1-s2.0-{pii}-{suffix}"
            if image_ok(u):
                return u, "graphical_abstract"
    meta = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
    if meta and meta.get("content"):
        u = urljoin(final, meta["content"])
        if image_ok(u):
            return u, "publisher_preview"
    return "", ""


def save_visual(url, title):
    if not url:
        return ""
    try:
        r = SESSION.get(url, timeout=35, allow_redirects=True)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if not ctype.startswith("image/") or len(r.content) < 2500 or len(r.content) > 12_000_000:
            return ""
        ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype.split(";")[0], ".jpg")
        name = hashlib.sha1(norm(title).encode()).hexdigest()[:14] + ext
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        path = IMG_DIR / name
        path.write_bytes(r.content)
        return f"assets/publications/{name}"
    except Exception as e:
        print("Visual download failed:", url, e)
        return ""


def refresh_visuals(pubs, limit=18):
    # Only the newest records need immediate visual checks; older entries remain searchable.
    for i, p in enumerate(pubs):
        if i >= limit:
            break
        existing = p.get("graphical_abstract", "")
        if existing and not existing.startswith("http") and (ROOT / existing).exists():
            continue
        if not p.get("doi"):
            p["doi"] = crossref_doi(p.get("title", ""))
        url, kind = discover_publisher_visual(p.get("doi", ""))
        local = save_visual(url, p.get("title", "")) if url else ""
        if local:
            p["graphical_abstract"] = local
            p["graphical_abstract_kind"] = kind
    return pubs


def write(data):
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    JS_PATH.write_text(
        "window.LAB_PUBLICATION_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


def main():
    old = load_old()
    source_sets = []
    source_labels = []
    metrics = dict(old.get("metrics", {}))

    key = os.getenv("SERPAPI_KEY", "").strip()
    if key:
        try:
            pubs = serpapi_publications(key)
            source_sets.append(("Google Scholar via SerpApi", pubs))
            source_labels.append(f"Google Scholar via SerpApi ({len(pubs)})")
        except Exception as e:
            print("SerpApi failed:", e)
    else:
        try:
            pubs = direct_scholar_publications()
            source_sets.append(("Google Scholar direct profile", pubs))
            source_labels.append(f"Google Scholar direct ({len(pubs)})")
        except Exception as e:
            print("Direct Scholar failed:", e)

    try:
        pubs, metrics = parse_sinta_google_scholar(metrics)
        source_sets.append(("SINTA Google Scholar mirror", pubs))
        source_labels.append(f"SINTA Scholar mirror ({len(pubs)})")
    except Exception as e:
        print("SINTA Scholar refresh failed:", e)

    try:
        pubs = researchgate_publications()
        source_sets.append(("ResearchGate public profile", pubs))
        source_labels.append(f"ResearchGate public profile ({len(pubs)})")
    except Exception as e:
        print("ResearchGate fallback failed:", e)

    try:
        pubs = crossref_orcid_publications()
        source_sets.append(("Crossref ORCID metadata", pubs))
        source_labels.append(f"Crossref ORCID ({len(pubs)})")
    except Exception as e:
        print("Crossref ORCID fallback failed:", e)

    try:
        pubs = openalex_orcid_publications()
        source_sets.append(("OpenAlex via ORCID", pubs))
        source_labels.append(f"OpenAlex ORCID ({len(pubs)})")
    except Exception as e:
        print("OpenAlex ORCID fallback failed:", e)

    if not source_sets:
        pubs = old.get("publications", [])
        if not pubs:
            raise RuntimeError("No publication source was reachable and no cached catalogue exists")
        source_sets = [("cached snapshot", pubs)]
        source_labels = [f"cached snapshot ({len(pubs)})"]

    pubs = merge_catalogue(source_sets, old)

    try:
        qmap = parse_sinta_scopus_quartiles()
        source_labels.append("SINTA quartiles")
    except Exception as e:
        print("Quartile refresh failed:", e)
        qmap = {}

    pubs = apply_quartiles_and_old_metadata(pubs, old, qmap)
    pubs.sort(key=lambda p: (p.get("year") or 0, p.get("citations") if p.get("citations") is not None else -1), reverse=True)

    # Translation is cached. New Scholar/registry items are translated automatically.
    pubs = refresh_title_translations(pubs)
    pubs = refresh_visuals(pubs)

    data = {
        "last_updated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": " / ".join(source_labels),
        "metrics": metrics,
        "publications": pubs,
    }
    write(data)
    print(f"Wrote {len(pubs)} searchable publications")


if __name__ == "__main__":
    main()

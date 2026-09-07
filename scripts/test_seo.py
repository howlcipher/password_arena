#!/usr/bin/env python3
"""Automated SEO verification script for Password Arena documentation.

Validates:
- HTML title and meta description presence and length limits
- Canonical URLs
- Exactly one H1 tag per page
- Open Graph and Twitter Card tags
- JSON-LD SoftwareApplication schema attributing William Elias
- robots.txt and sitemap.xml files
"""

import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET


def test_page(file_path: str, expected_canonical: str) -> None:
    print(f"Testing page: {file_path}")
    if not os.path.isfile(file_path):
        print(f"  [FAIL] Missing HTML file: {file_path}")
        sys.exit(1)

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Title
    title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    if not title_match:
        print("  [FAIL] Missing <title> tag")
        sys.exit(1)
    title = title_match.group(1).strip()
    print(f"  [PASS] HTML <title> exists: {html.unescape(title)}")

    # Meta description
    desc_regex_1 = r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']'
    desc_regex_2 = r'<meta\s+content=["\'](.*?)["\']\s+name=["\']description["\']'
    desc_match = re.search(desc_regex_1, content, re.IGNORECASE) or re.search(
        desc_regex_2, content, re.IGNORECASE
    )
    if not desc_match:
        print("  [FAIL] Missing meta description")
        sys.exit(1)
    desc = desc_match.group(1).strip()
    if len(desc) > 165:
        print(f"  [FAIL] Meta description too long ({len(desc)} > 165 chars): {desc}")
        sys.exit(1)
    print(f"  [PASS] meta description exists: {desc[:60]}... ({len(desc)} chars)")

    # Canonical URL
    canon_regex = r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']'
    canon_match = re.search(canon_regex, content, re.IGNORECASE)
    if not canon_match:
        print("  [FAIL] Missing canonical URL link tag")
        sys.exit(1)
    canon_url = canon_match.group(1).strip()
    if canon_url != expected_canonical:
        print(f"  [FAIL] Canonical URL mismatch: expected {expected_canonical}, got {canon_url}")
        sys.exit(1)
    print(f"  [PASS] Canonical URL matches: {canon_url}")

    # Exactly 1 H1
    h1_matches = re.findall(r"<h1\b[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
    if len(h1_matches) != 1:
        print(f"  [FAIL] Expected exactly 1 H1 tag, found {len(h1_matches)}")
        sys.exit(1)
    h1_text = re.sub(r"<[^>]+>", "", h1_matches[0]).strip()
    print(f"  [PASS] Exactly 1 H1 present: {h1_text}")

    # Open Graph & Twitter Cards
    og_title = re.search(r'<meta\s+property=["\']og:title["\']', content, re.IGNORECASE)
    og_desc = re.search(r'<meta\s+property=["\']og:description["\']', content, re.IGNORECASE)
    tw_card = re.search(r'<meta\s+name=["\']twitter:card["\']', content, re.IGNORECASE)
    if not (og_title and og_desc and tw_card):
        print("  [FAIL] Incomplete Open Graph / Twitter Card tags")
        sys.exit(1)
    print("  [PASS] Open Graph and Twitter card tags verified")

    # JSON-LD
    json_ld_regex = r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>'
    json_ld_match = re.search(json_ld_regex, content, re.IGNORECASE | re.DOTALL)
    if not json_ld_match:
        print("  [FAIL] Missing JSON-LD script block")
        sys.exit(1)
    try:
        data = json.loads(json_ld_match.group(1).strip())
        if data.get("@type") != "SoftwareApplication":
            print(f"  [FAIL] JSON-LD @type is {data.get('@type')}, expected SoftwareApplication")
            sys.exit(1)
        author = data.get("author", {})
        if author.get("name") != "William Elias":
            print(f"  [FAIL] Author name is {author.get('name')}, expected William Elias")
            sys.exit(1)
        print("  [PASS] JSON-LD valid and correctly attributes William Elias")
    except Exception as e:
        print(f"  [FAIL] Invalid JSON-LD: {e}")
        sys.exit(1)

    # Internal links
    if "https://howlcipher.github.io/william_elias/" not in content:
        print("  [FAIL] Missing link to William Elias portfolio hub")
        sys.exit(1)
    print("  [PASS] Internal entity link to William Elias verified")


def test_seo():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(repo_root, "docs")
    index_html = os.path.join(docs_dir, "index.html")
    benchmarks_html = os.path.join(docs_dir, "benchmarks.html")
    robots_path = os.path.join(docs_dir, "robots.txt")
    sitemap_path = os.path.join(docs_dir, "sitemap.xml")

    print("=== Running Password Arena SEO Verification ===")

    test_page(index_html, "https://howlcipher.github.io/password_arena/")
    test_page(benchmarks_html, "https://howlcipher.github.io/password_arena/benchmarks.html")

    # robots.txt
    if not os.path.isfile(robots_path):
        print(f"  [FAIL] Missing robots.txt at {robots_path}")
        sys.exit(1)
    with open(robots_path, encoding="utf-8") as f:
        robots_content = f.read()
    sitemap_url = "https://howlcipher.github.io/password_arena/sitemap.xml"
    if "Sitemap:" not in robots_content or sitemap_url not in robots_content:
        print("  [FAIL] robots.txt does not properly reference sitemap.xml")
        sys.exit(1)
    print("  [PASS] docs/robots.txt valid and references sitemap")

    # sitemap.xml
    if not os.path.isfile(sitemap_path):
        print(f"  [FAIL] Missing sitemap.xml at {sitemap_path}")
        sys.exit(1)
    try:
        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        urls = [
            elem.text for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        ]
        expected_urls = [
            "https://howlcipher.github.io/password_arena/",
            "https://howlcipher.github.io/password_arena/benchmarks.html",
        ]
        for url in expected_urls:
            if url not in urls:
                print(f"  [FAIL] sitemap.xml missing URL: {url}")
                sys.exit(1)
        print("  [PASS] docs/sitemap.xml valid and contains all canonical URLs")
    except Exception as e:
        print(f"  [FAIL] Malformed sitemap.xml: {e}")
        sys.exit(1)

    print("\nAll Password Arena SEO validations PASSED successfully!")


if __name__ == "__main__":
    test_seo()

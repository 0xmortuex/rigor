#!/usr/bin/env python3
"""Vendor a subset of web-platform-tests reftests under tools/vendor/wpt.

A reftest is two pages that must render identically: the test, and the
reference it names with `<link rel=match>`. That is a format rigor can run
without JavaScript, which is why it is the part of WPT vendored here.

Tests that need something rigor has no answer for are left out at fetch time
rather than skipped at run time, and the reason is recorded in the manifest so
the exclusions are visible rather than implied:

    ahem        needs the Ahem font, whose glyphs are exact squares; without
                it every text position in the test is wrong for reasons that
                have nothing to do with what the test checks
    script      needs JavaScript
    mismatch    a `rel=mismatch` reftest, which asserts two pages differ —
                a weaker check that rigor would pass by rendering nothing

    python tools/fetch_wpt.py css/CSS2/floats css/CSS2/normal-flow

Re-running replaces the vendored copy and rewrites the manifest.
"""

import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENDOR = os.path.join(HERE, "vendor", "wpt")
API = "https://api.github.com/repos/web-platform-tests/wpt/contents/"
RAW = "https://raw.githubusercontent.com/web-platform-tests/wpt/master/"


def get(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "rigor-wpt-fetch",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(request) as response:
        return response.read()


def list_directory(path):
    return json.loads(get(API + path + "?ref=master"))


MATCH = re.compile(rb'<link[^>]*\brel\s*=\s*["\']?match["\']?[^>]*>', re.I)
MISMATCH = re.compile(rb'<link[^>]*\brel\s*=\s*["\']?mismatch["\']?[^>]*>', re.I)
HREF = re.compile(rb'href\s*=\s*["\']([^"\']+)["\']', re.I)


def classify(body):
    """Why this test cannot be run, or None when it can."""
    lowered = body.lower()
    if b"ahem" in lowered:
        return "ahem"
    if b"<script" in lowered:
        return "script"
    if MISMATCH.search(body):
        return "mismatch"
    if not MATCH.search(body):
        return "not-a-reftest"
    return None


def reference_of(body):
    tag = MATCH.search(body)
    if not tag:
        return None
    href = HREF.search(tag.group(0))
    if not href:
        return None
    return href.group(1).decode("utf-8", "replace")


def main():
    directories = sys.argv[1:] or ["css/CSS2/floats"]
    os.makedirs(VENDOR, exist_ok=True)

    manifest = []
    excluded = {}
    for directory in directories:
        print(f"listing {directory}")
        entries = list_directory(directory)
        files = {e["name"]: e for e in entries if e["type"] == "file"}
        out_dir = os.path.join(VENDOR, directory.replace("/", os.sep))
        os.makedirs(out_dir, exist_ok=True)

        for name, entry in sorted(files.items()):
            if not name.endswith(".html") and not name.endswith(".htm"):
                continue
            body = get(RAW + directory + "/" + name)
            reason = classify(body)
            if reason is not None:
                if reason != "not-a-reftest":
                    excluded[reason] = excluded.get(reason, 0) + 1
                continue
            reference = reference_of(body)
            if reference is None or reference.startswith("/") \
                    or "/" in reference:
                # References outside the directory would drag in support trees;
                # the vendored set stays flat.
                excluded["external-ref"] = excluded.get("external-ref", 0) + 1
                continue
            if reference not in files:
                excluded["missing-ref"] = excluded.get("missing-ref", 0) + 1
                continue
            reference_body = get(RAW + directory + "/" + reference)
            if classify(reference_body) not in (None, "not-a-reftest"):
                excluded["ahem-ref"] = excluded.get("ahem-ref", 0) + 1
                continue

            with open(os.path.join(out_dir, name), "wb") as handle:
                handle.write(body)
            with open(os.path.join(out_dir, reference), "wb") as handle:
                handle.write(reference_body)
            manifest.append({
                "directory": directory,
                "test": name,
                "reference": reference,
            })
            print(f"  {name} -> {reference}")

    with open(os.path.join(VENDOR, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump({"tests": manifest, "excluded": excluded}, handle, indent=2)
    print(f"\n{len(manifest)} reftests vendored")
    for reason, count in sorted(excluded.items()):
        print(f"  excluded {count} for: {reason}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the vendored web-platform-tests reftests against rigor.

A reftest passes when the test page and the page it names with
`<link rel=match>` render identically. Both are rendered by rigor, so any
difference between them is a difference in rigor's own behaviour — which is
what makes this a check on the engine rather than on the font stack.

Comparison is over WPT's 800x600 viewport: the first 600 rows of an 800-wide
render, padded with the canvas background where a page is shorter. Pixels must
match exactly; a reftest that is "nearly right" is wrong, because the reference
was written to produce the same pixels by a different route.

    python tools/run_wpt.py
    python tools/run_wpt.py -v --failures 5
"""

import argparse
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENDOR = os.path.join(HERE, "vendor", "wpt")
RIGOR = os.path.join(ROOT, "build",
                     "rigor.exe" if os.name == "nt" else "rigor")

VIEWPORT_WIDTH = 800
VIEWPORT_HEIGHT = 600


def render(path, out_path):
    """Render one page and return its BMP bytes, or None on failure."""
    environment = dict(os.environ)
    environment["RIGOR_OUT"] = out_path
    environment.pop("RIGOR_URL", None)
    with open(path, "rb") as handle:
        body = handle.read()
    result = subprocess.run([RIGOR], input=body, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, env=environment,
                            cwd=os.path.dirname(path))
    if result.returncode != 0:
        return None
    if not os.path.isfile(out_path):
        return None
    with open(out_path, "rb") as handle:
        return handle.read()


def viewport_rows(bmp):
    """The viewport's pixels, as a list of rows of (b, g, r) tuples."""
    if bmp is None or len(bmp) < 54 or bmp[:2] != b"BM":
        return None
    offset = struct.unpack("<I", bmp[10:14])[0]
    width = struct.unpack("<i", bmp[18:22])[0]
    height = struct.unpack("<i", bmp[22:26])[0]
    bottom_up = height > 0
    height = abs(height)
    rows = []
    for y in range(VIEWPORT_HEIGHT):
        if y >= height:
            # Past the end of a short page: the canvas background, which paint
            # fills white.
            rows.append(b"\xff\xff\xff\xff" * min(width, VIEWPORT_WIDTH))
            continue
        source = (height - 1 - y) if bottom_up else y
        start = offset + source * width * 4
        rows.append(bmp[start:start + min(width, VIEWPORT_WIDTH) * 4])
    return rows


def compare(test_bmp, reference_bmp):
    """Number of differing pixels in the viewport, or None if unreadable."""
    left = viewport_rows(test_bmp)
    right = viewport_rows(reference_bmp)
    if left is None or right is None:
        return None
    differences = 0
    first = None
    for y, (a, b) in enumerate(zip(left, right)):
        if a == b:
            continue
        for x in range(0, min(len(a), len(b)), 4):
            if a[x:x + 4] != b[x:x + 4]:
                differences += 1
                if first is None:
                    first = (x // 4, y)
    return differences, first


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--failures", type=int, default=10)
    parser.add_argument("--filter")
    args = parser.parse_args()

    manifest_path = os.path.join(VENDOR, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise SystemExit(
            f"no vendored tests at {VENDOR}\n"
            "fetch them first: python tools/fetch_wpt.py css/CSS2/floats")
    if not os.path.isfile(RIGOR):
        raise SystemExit(f"missing {RIGOR}\nbuild it first: mortc build")

    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    scratch = os.path.join(VENDOR, ".render")
    os.makedirs(scratch, exist_ok=True)
    test_out = os.path.join(scratch, "test.bmp")
    reference_out = os.path.join(scratch, "reference.bmp")

    by_directory = {}
    failures = []
    errors = 0
    for entry in manifest["tests"]:
        if args.filter and args.filter not in entry["test"]:
            continue
        directory = os.path.join(VENDOR, entry["directory"].replace("/", os.sep))
        stats = by_directory.setdefault(entry["directory"], [0, 0])
        stats[1] += 1

        test_bmp = render(os.path.join(directory, entry["test"]), test_out)
        reference_bmp = render(os.path.join(directory, entry["reference"]),
                               reference_out)
        result = compare(test_bmp, reference_bmp)
        if result is None:
            errors += 1
            failures.append((entry, "did not render"))
            continue
        differences, first = result
        if differences == 0:
            stats[0] += 1
        else:
            where = f" (first at {first[0]},{first[1]})" if first else ""
            failures.append((entry, f"{differences} pixels differ{where}"))

    print("rigor vs web-platform-tests reftests\n")
    total = sum(stats[1] for stats in by_directory.values())
    passed = sum(stats[0] for stats in by_directory.values())
    width = max((len(name) for name in by_directory), default=10)
    for directory in sorted(by_directory):
        good, count = by_directory[directory]
        print(f"  {directory:<{width}}  {good:>3}/{count:<3} "
              f"{100.0 * good / count if count else 0:6.2f}%")
    print(f"\n  {'TOTAL':<{width}}  {passed:>3}/{total:<3} "
          f"{100.0 * passed / total if total else 0:6.2f}%")

    excluded = manifest.get("excluded", {})
    if excluded:
        print("\n  not vendored, and why:")
        for reason, count in sorted(excluded.items()):
            print(f"    {count:>3}  {reason}")

    if args.verbose and failures:
        print(f"\nfirst {min(args.failures, len(failures))} failures:\n")
        for entry, why in failures[:args.failures]:
            print(f"  {entry['directory']}/{entry['test']}")
            print(f"    vs {entry['reference']}: {why}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

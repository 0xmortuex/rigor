#!/usr/bin/env python3
"""Run the html5lib-tests tree-construction suites against rigor.

The .dat suites are vendored under tools/vendor/html5lib-tests/tree-construction
(pinned in ../PINNED). Each case is a #data block, the expected #errors, and a
#document section holding the expected tree in html5lib's serialization —
exactly the format engine/src/dom/serialize.mx emits, so comparison is a
line-for-line diff.

    python tools/run_tree_conformance.py
    python tools/run_tree_conformance.py -v --failures 5
    python tools/run_tree_conformance.py --file adoption01.dat

Fragment cases (#document-fragment) and script-on cases are skipped and
counted, never silently passed: fragment parsing and scripting are not
implemented.
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUITE_DIR = os.path.join(HERE, "vendor", "html5lib-tests", "tree-construction")
HARNESS_BIN = os.path.join(
    ROOT, "conformance", "build",
    "rigor_conformance.exe" if os.name == "nt" else "rigor_conformance")


def parse_dat(path):
    """Split a .dat file into its cases."""
    with open(path, "r", encoding="utf-8", newline="\n") as handle:
        text = handle.read()
    cases = []
    # Cases are separated by a blank line followed by "#data".
    chunks = text.split("\n\n#data\n")
    if chunks and chunks[0].startswith("#data\n"):
        chunks[0] = chunks[0][len("#data\n"):]
    for chunk in chunks:
        section = "data"
        buckets = {"data": [], "errors": [], "document": [],
                   "document-fragment": [], "script-on": [], "script-off": [],
                   "new-errors": []}
        for line in chunk.split("\n"):
            if line.startswith("#") and line[1:] in buckets:
                section = line[1:]
                continue
            if line.startswith("#") and line[1:] in (
                    "data", "errors", "document", "document-fragment",
                    "script-on", "script-off", "new-errors"):
                section = line[1:]
                continue
            buckets[section].append(line)
        # The document section's trailing blank line is a separator artifact.
        document = buckets["document"]
        while document and document[-1] == "":
            document.pop()
        cases.append({
            "input": "\n".join(buckets["data"]),
            "document": "\n".join(document),
            "fragment": "\n".join(buckets["document-fragment"]).strip(),
            "script_on": bool([l for l in buckets["script-on"] if l.strip()]),
        })
    return cases


def load_cases(only_file=None):
    cases = []
    skipped = 0
    names = sorted(f for f in os.listdir(SUITE_DIR) if f.endswith(".dat"))
    if only_file:
        names = [n for n in names if n == only_file]
        if not names:
            raise SystemExit(f"no vendored suite named {only_file!r}")
    for name in names:
        for index, case in enumerate(parse_dat(os.path.join(SUITE_DIR, name))):
            if case["fragment"] or case["script_on"]:
                skipped += 1
                continue
            if not case["input"] and not case["document"]:
                continue
            case["label"] = f"{name}#{index}"
            case["suite"] = name
            cases.append(case)
    return cases, skipped


def run_harness(cases):
    if not os.path.isfile(HARNESS_BIN):
        raise SystemExit(
            f"missing {HARNESS_BIN}\nbuild it first: cd conformance && mortc build")
    job = json.dumps(
        {"mode": "tree", "cases": [{"input": c["input"]} for c in cases]},
        ensure_ascii=True)
    process = subprocess.run(
        [HARNESS_BIN], input=job.encode("ascii"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        sys.stderr.write(process.stderr.decode("utf-8", "replace"))
        raise SystemExit(f"harness exited {process.returncode}")
    lines = [line for line in process.stdout.decode("ascii").splitlines() if line]
    if len(lines) != len(cases):
        raise SystemExit(
            f"harness returned {len(lines)} results for {len(cases)} cases")
    return [json.loads(line)["tree"] for line in lines]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--failures", type=int, default=10)
    parser.add_argument("--file")
    args = parser.parse_args()

    cases, skipped = load_cases(args.file)
    trees = run_harness(cases)

    by_suite = {}
    failures = []
    for case, tree in zip(cases, trees):
        stats = by_suite.setdefault(case["suite"], [0, 0])
        stats[1] += 1
        got = tree.rstrip("\n")
        want = case["document"].rstrip("\n")
        if got == want:
            stats[0] += 1
        else:
            failures.append((case, got))

    total = len(cases)
    passed = sum(stats[0] for stats in by_suite.values())
    print("rigor tree construction vs html5lib-tests\n")
    width = max((len(n) for n in by_suite), default=10)
    for suite in sorted(by_suite):
        good, count = by_suite[suite]
        print(f"  {suite:<{width}}  {good:>4}/{count:<4} "
              f"{100.0 * good / count if count else 0:6.2f}%")
    print(f"\n  {'TOTAL':<{width}}  {passed:>4}/{total:<4} "
          f"{100.0 * passed / total if total else 0:6.2f}%")
    if skipped:
        print(f"  {'skipped':<{width}}  {skipped:>4}       "
              f"(fragment parsing / scripting, not implemented)")

    if args.verbose and failures:
        print(f"\nfirst {min(args.failures, len(failures))} failures:\n")
        for case, got in failures[:args.failures]:
            print(f"  {case['label']}")
            print(f"    input    {case['input']!r}")
            print("    expected")
            for line in case["document"].split("\n"):
                print(f"      {line}")
            print("    got")
            for line in got.split("\n"):
                print(f"      {line}")
            print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Map exported Android activities to Intent extras read in onCreate/onNewIntent.

Designed for JADX decompiled source output. Static analysis only: results can be
missed when values flow through helper methods/wrappers or non-literal constants.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

EXTRA_METHODS = {
    "getStringExtra": "String",
    "getIntExtra": "int",
    "getLongExtra": "long",
    "getBooleanExtra": "boolean",
    "getFloatExtra": "float",
    "getDoubleExtra": "double",
    "getByteExtra": "byte",
    "getShortExtra": "short",
    "getCharExtra": "char",
    "getStringArrayExtra": "String[]",
    "getStringArrayListExtra": "ArrayList<String>",
    "getIntArrayExtra": "int[]",
    "getBooleanArrayExtra": "boolean[]",
    "getBundleExtra": "Bundle",
    "getParcelableExtra": "Parcelable",
    "getParcelableArrayExtra": "Parcelable[]",
    "getParcelableArrayListExtra": "ArrayList<Parcelable>",
    "getSerializableExtra": "Serializable",
    "getCharSequenceExtra": "CharSequence",
    "getCharSequenceArrayExtra": "CharSequence[]",
    "getCharSequenceArrayListExtra": "ArrayList<CharSequence>",
}

@dataclass
class Component:
    manifest_name: str
    code_name: str
    exported: bool
    export_reason: str
    kind: str


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def resolve_class(name: Optional[str], package: str) -> Optional[str]:
    if not name:
        return None
    if name.startswith("."):
        return package + name
    if "." not in name:
        return package + "." + name if package else name
    return name


def find_manifest(root: Path, explicit: Optional[Path]) -> Path:
    if explicit:
        path = explicit.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Manifest not found: {path}")
        return path
    candidates = list(root.rglob("AndroidManifest.xml"))
    if not candidates:
        raise FileNotFoundError("AndroidManifest.xml was not found under InputPath")
    # Prefer JADX's decoded resources manifest when multiple copies exist.
    candidates.sort(key=lambda p: ("resources" not in p.parts, len(p.parts)))
    return candidates[0]


def read_components(manifest: Path) -> tuple[list[Component], str, str]:
    tree = ET.parse(manifest)
    app = tree.getroot()
    package = app.attrib.get("package", "")
    target_sdk = "unknown"
    for node in app:
        if local_name(node.tag) == "uses-sdk":
            target_sdk = node.attrib.get(ANDROID_NS + "targetSdkVersion", "unknown")
            break

    components: list[Component] = []
    for node in app.iter():
        tag = local_name(node.tag)
        if tag not in ("activity", "activity-alias"):
            continue
        manifest_name = resolve_class(node.attrib.get(ANDROID_NS + "name"), package)
        target = resolve_class(node.attrib.get(ANDROID_NS + "targetActivity"), package) if tag == "activity-alias" else manifest_name
        if not manifest_name or not target:
            continue
        raw_exported = node.attrib.get(ANDROID_NS + "exported")
        has_filter = any(local_name(child.tag) == "intent-filter" for child in node)
        if raw_exported is not None:
            exported = raw_exported.lower() == "true"
            reason = f"android:exported={raw_exported}"
        elif has_filter:
            try:
                legacy_default = int(target_sdk) <= 30
            except ValueError:
                legacy_default = False
            exported = legacy_default
            reason = "intent-filter; legacy default=true" if legacy_default else "intent-filter; exported not explicit (review manifest/build target)"
        else:
            exported = False
            reason = "no android:exported=true and no intent-filter"
        components.append(Component(manifest_name, target, exported, reason, tag))
    return components, package, target_sdk


def find_source(root: Path, class_name: str) -> Optional[Path]:
    relative = Path(*class_name.split("."))
    for base in (root / "sources", root):
        for suffix in (".java", ".kt"):
            candidate = base / relative.with_suffix(suffix)
            if candidate.is_file():
                return candidate
    # Fallback for unusual JADX layouts or package/class path mismatch.
    simple = class_name.rsplit(".", 1)[-1]
    matches = [p for p in root.rglob(simple + ".java")]
    if not matches:
        matches = [p for p in root.rglob(simple + ".kt")]
    return matches[0] if len(matches) == 1 else None


def extract_method_bodies(source: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    # JADX Java is the primary target; Kotlin-like declarations are included as a best effort.
    pattern = re.compile(r"\b(onCreate|onNewIntent)\s*\([^)]*\)\s*(?:throws\s+[^\{]+)?\{")
    for match in pattern.finditer(source):
        brace_start = source.find("{", match.start())
        depth = 0
        in_string = in_char = in_line_comment = in_block_comment = escaped = False
        end = None
        i = brace_start
        while i < len(source):
            ch = source[i]
            nxt = source[i + 1] if i + 1 < len(source) else ""
            if in_line_comment:
                if ch == "\n": in_line_comment = False
            elif in_block_comment:
                if ch == "*" and nxt == "/": in_block_comment = False; i += 1
            elif in_string:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == '"': in_string = False
            elif in_char:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == "'": in_char = False
            elif ch == "/" and nxt == "/": in_line_comment = True; i += 1
            elif ch == "/" and nxt == "*": in_block_comment = True; i += 1
            elif ch == '"': in_string = True
            elif ch == "'": in_char = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
            i += 1
        if end is not None:
            found.append((match.group(1), source[brace_start + 1:end]))
    return found


def parse_first_argument(text: str) -> tuple[str, str]:
    """Return (key, confidence); only resolve a simple quoted literal."""
    text = text.lstrip()
    if text.startswith('"'):
        escaped = False
        chars = []
        for ch in text[1:]:
            if escaped:
                chars.append(ch); escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                return "".join(chars), "literal"
            else:
                chars.append(ch)
    # Constants such as EXTRA_USERNAME are recorded, not evaluated.
    token = re.match(r"[A-Za-z_$][\w.$]*", text)
    if token:
        return token.group(0), "constant_or_expression"
    return "<dynamic-or-unresolved>", "unresolved"


def scan_method_body(body: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    method_names = "|".join(sorted(map(re.escape, EXTRA_METHODS), key=len, reverse=True))
    call_re = re.compile(r"\b(" + method_names + r")\s*\(")
    for match in call_re.finditer(body):
        # Capture first argument while respecting nested parentheses and strings.
        start = match.end()
        depth = 0
        in_string = escaped = False
        comma = None
        end = None
        for i in range(start, len(body)):
            ch = body[i]
            if in_string:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == '"': in_string = False
                continue
            if ch == '"': in_string = True
            elif ch == "(": depth += 1
            elif ch == ")":
                if depth == 0:
                    end = i; break
                depth -= 1
            elif ch == "," and depth == 0 and comma is None:
                comma = i
        arg_end = comma if comma is not None else (end if end is not None else start)
        key, confidence = parse_first_argument(body[start:arg_end])
        results.append({"key": key, "type": EXTRA_METHODS[match.group(1)], "method": match.group(1), "confidence": confidence})
    # getExtras() exposes a Bundle, but does not reveal its individual keys here.
    if re.search(r"\bgetExtras\s*\(", body):
        results.append({"key": "<Bundle keys not statically enumerated>", "type": "Bundle", "method": "getExtras", "confidence": "manual_review"})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Find Intent extras read by exported Android activities in JADX output.")
    parser.add_argument("-InputPath", required=True, help="JADX output directory")
    parser.add_argument("-OutputPath", help="CSV report path (default: Intent-Extras-Report.csv in input directory)")
    parser.add_argument("-ManifestPath", help="Optional explicit AndroidManifest.xml path")
    args = parser.parse_args()

    root = Path(args.InputPath).expanduser().resolve()
    if not root.is_dir():
        print(f"[!] Input directory not found: {root}", file=sys.stderr)
        return 2
    manifest = find_manifest(root, Path(args.ManifestPath) if args.ManifestPath else None)
    components, package, target_sdk = read_components(manifest)
    exported = [c for c in components if c.exported]
    rows: list[dict[str, str]] = []

    print(f"[*] Manifest       : {manifest}")
    print(f"[*] Package        : {package or 'unknown'}")
    print(f"[*] Target SDK     : {target_sdk}")
    print(f"[*] Exported       : {len(exported)} activity components")

    for component in exported:
        source_path = find_source(root, component.code_name)
        base = {
            "activity": component.manifest_name,
            "code_class": component.code_name,
            "component_type": component.kind,
            "export_reason": component.export_reason,
            "source_file": str(source_path.relative_to(root)) if source_path else "NOT_FOUND",
        }
        if not source_path:
            rows.append({**base, "method_scope": "", "extra_key": "", "extra_type": "", "getter": "", "key_confidence": "source_not_found", "status": "Source not found"})
            continue
        try:
            source = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            rows.append({**base, "method_scope": "", "extra_key": "", "extra_type": "", "getter": "", "key_confidence": "read_error", "status": "Source unreadable"})
            continue
        methods = extract_method_bodies(source)
        activity_hits = []
        for method_name, body in methods:
            for hit in scan_method_body(body):
                activity_hits.append({**base, "method_scope": method_name, "extra_key": hit["key"], "extra_type": hit["type"], "getter": hit["method"], "key_confidence": hit["confidence"], "status": "Extra detected"})
        if activity_hits:
            rows.extend(activity_hits)
        else:
            rows.append({**base, "method_scope": "onCreate/onNewIntent", "extra_key": "", "extra_type": "", "getter": "", "key_confidence": "", "status": "No extras detected in onCreate/onNewIntent"})

    output = Path(args.OutputPath).expanduser().resolve() if args.OutputPath else root / "Intent-Extras-Report.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["activity", "code_class", "component_type", "export_reason", "source_file", "method_scope", "extra_key", "extra_type", "getter", "key_confidence", "status"]
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    detected = sum(1 for row in rows if row["status"] == "Extra detected")
    missing = sum(1 for row in rows if row["status"] == "No extras detected in onCreate/onNewIntent")
    unresolved = sum(1 for row in rows if row["status"] in ("Source not found", "Source unreadable"))
    print(f"[+] Extra reads     : {detected}")
    print(f"[+] No extras found : {missing}")
    print(f"[!] Review needed   : {unresolved}")
    print(f"[+] CSV report      : {output}")
    print("[!] Static analysis only: helper methods, wrappers, reflection, dynamic keys, and indirect Intent flows may be missed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

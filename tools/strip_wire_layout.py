#!/usr/bin/env python3
"""Strip the per-type layout hash from the Wire trait's impls (#1279).

The loader no longer compares `Wire::layout`; call names hashed by the surface crate's
`shape` replace it. This removes, from every Rust file under the Wire crates:

  * `const LAYOUT_SEED: u64 = ...;`
  * `fn layout(visiting) -> u64 { ... }` of an impl (and `__field_layouts`, `__tuple_layouts`),
    with the doc comments and attributes written directly above it
  * `#[wire(internal_field_layouts)]`, which only fed `__field_layouts`

An impl whose `fn layout` returned another type's layout (`T::layout(visiting)`) keeps that
declaration as `layout_via!(T);`, read by the surface export in place of the removed body.
Impls keep `put`, `put_owned`, `take` and `MIN`; `layout_fields!` stays as a declaration.

Not touched (done by hand after): the Wire trait itself, the `layout_fields!` macro
definition, the derive (`sunrise-mod-api-macros`), the free helpers and the tests of the hash.

Usage: python3 tools/strip_wire_layout.py [--check]   (from the repository root)
"""
import re
import sys
from pathlib import Path

ROOTS = [
    "crates/sunrise-mod-vocab",
    "crates/sunrise-mod-api",
    "crates/sunrise-mod-point-shape",
]
# Files whose `fn layout` is a std-type forwarding impl, not an API type's declared form.
NO_VIA = {"crates/sunrise-mod-vocab/src/wire/mod.rs"}
REMOVED_FNS = ("layout", "__field_layouts", "__tuple_layouts")


def skip_literal(src, i):
    """If a string, char or comment starts at `i`, the index after it; else `i`."""
    if src.startswith("//", i):
        j = src.find("\n", i)
        return len(src) if j < 0 else j
    if src.startswith("/*", i):
        j = src.find("*/", i)
        return len(src) if j < 0 else j + 2
    if src[i] == '"':
        j = i + 1
        while src[j] != '"':
            j += 2 if src[j] == "\\" else 1
        return j + 1
    if src[i] == "r" and re.match(r'r#*"', src[i:]):
        hashes = re.match(r"r(#*)", src[i:]).group(1)
        j = src.find('"' + hashes, src.find('"', i) + 1)
        return j + 1 + len(hashes)
    m = re.match(r"'(?:[^'\\]|\\[^']*)'", src[i:])
    if src[i] == "'" and m:
        return i + m.end()
    return i


def item_end(src, i, until_semi):
    """The index after the item starting at `i`: its `;` at depth 0, or its closing brace."""
    depth = 0
    while i < len(src):
        j = skip_literal(src, i)
        if j != i:
            i = j
            continue
        c = src[i]
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth -= 1
            if depth == 0 and c == "}" and not until_semi:
                return i + 1
        elif c == ";" and depth == 0 and until_semi:
            return i + 1
        i += 1
    raise ValueError("unterminated item")


def line_start(src, i):
    return src.rfind("\n", 0, i) + 1


def with_leading_lines(src, start):
    """`start` moved up over the doc comments, comments and attributes directly above it."""
    while True:
        prev_end = line_start(src, start) - 1
        if prev_end < 0:
            return start
        prev = src[line_start(src, prev_end) : prev_end]
        if re.match(r"\s*(///|//|#\[)", prev):
            start = line_start(src, prev_end)
        else:
            return start


VIA = re.compile(
    r"^\s*\{\s*(?:<\s*(?P<q>.+?)\s+as\s+(?:[\w:]*::)?Wire\s*>|(?P<p>[\w:<>, ]+?))::layout\([^)]*\)\s*\}\s*$",
    re.S,
)


def strip(path, src):
    rel = str(path)
    out = src
    via_for_impl = []
    # `fn layout` / `__field_layouts` / `__tuple_layouts`, longest-start first so offsets hold.
    spans = []
    for m in re.finditer(r"^[ \t]*(?:pub(?:\([^)]*\))? )?fn (%s)\b" % "|".join(REMOVED_FNS), out, re.M):
        body_open = out.index("{", m.end())
        # The `{` must come after the signature's `->` type, which holds no braces.
        end = item_end(out, body_open, False)
        end = out.index("\n", end) + 1 if "\n" in out[end : end + 2] else end
        body = out[body_open : end].rstrip()
        via = None
        if m.group(1) == "layout" and rel not in NO_VIA:
            v = VIA.match(body)
            if v and (v.group("q") or v.group("p")) and (v.group("q") or "Self" != v.group("p").strip()):
                via = (v.group("q") or v.group("p")).strip()
        spans.append((with_leading_lines(out, m.start()), end, via, m.start()))
    # `const LAYOUT_SEED: u64 = ...;` (not the trait's own declaration, which has no value)
    for m in re.finditer(r"^[ \t]*const LAYOUT_SEED: u64 =\s*", out, re.M):
        end = item_end(out, m.end(), True)
        end = out.index("\n", end) + 1 if "\n" in out[end : end + 2] else end
        spans.append((with_leading_lines(out, m.start()), end, None, m.start()))
    for start, end, via, at in sorted(spans, reverse=True):
        indent = re.match(r"[ \t]*", out[at : at + 80]).group(0)
        repl = f"{indent}layout_via!({via});\n" if via else ""
        out = out[:start] + repl + out[end:]
    out = re.sub(r"^[ \t]*#\[wire\(internal_field_layouts\)\]\n", "", out, flags=re.M)
    return out


def main():
    check = "--check" in sys.argv
    changed = 0
    for root in ROOTS:
        for path in sorted(Path(root).rglob("*.rs")):
            src = path.read_text()
            new = strip(path, src)
            if new != src:
                changed += 1
                if not check:
                    path.write_text(new)
    print(f"{'would change' if check else 'changed'} {changed} files")


if __name__ == "__main__":
    main()

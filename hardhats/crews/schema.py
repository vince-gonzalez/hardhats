"""
hardHats crew: the Schema crew (keyword `schema`). A database architect's read on SQL DDL: does
every table have a primary key, is every foreign key indexed, and are there obvious denormalised
repeating groups? Deterministic (zero model calls); relational-design conventions.

A table with no primary key has no identity - you cannot reliably update or dedupe a row. A foreign
key with no index turns every join and every cascade into a scan. Those are structural facts in the
DDL, settled without a running database. It does NOT read query plans, judge data types, or know
your access patterns - that is a DBA's call against real EXPLAIN output.

    python -m hardhats.crews.schema <schema.sql> [--md out.md]

Exit 1 if a table has no primary key.
"""
from __future__ import annotations

import os
import re
import sys

CREATE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?[\"'`\[]?([A-Za-z_][\w.]*)[\"'`\]]?\s*\(",
                    re.I)


def _strip_comments(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _balanced(sql, open_idx):
    depth, j = 0, open_idx
    while j < len(sql):
        if sql[j] == "(":
            depth += 1
        elif sql[j] == ")":
            depth -= 1
            if depth == 0:
                return sql[open_idx + 1:j]
        j += 1
    return sql[open_idx + 1:]


def _col_defs(body):
    """Split a CREATE TABLE body on top-level commas into column / constraint clauses."""
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def review(sql, log=print):
    sql = _strip_comments(sql)
    # indexes declared anywhere: table -> set(columns)
    indexed = {}
    for m in re.finditer(r"create\s+(?:unique\s+)?index\s+[\w.\"'`\[\]]+\s+on\s+[\"'`\[]?([A-Za-z_][\w.]*)[\"'`\]]?\s*\(([^)]+)\)", sql, re.I):
        tbl = m.group(1).lower()
        cols = {c.strip().strip('"\'`[] ').lower().split()[0] for c in m.group(2).split(",") if c.strip()}
        indexed.setdefault(tbl, set()).update(cols)

    tables, no_pk, unindexed_fk, repeating = [], [], [], []
    for m in CREATE.finditer(sql):
        name = m.group(1)
        body = _balanced(sql, m.end() - 1)
        tables.append(name)
        clauses = _col_defs(body)
        has_pk = bool(re.search(r"\bprimary\s+key\b", body, re.I))
        pk_cols = set()
        for c in clauses:
            if re.search(r"\bprimary\s+key\b", c, re.I):
                inline = re.match(r"[\"'`\[]?([A-Za-z_]\w*)", c)
                mt = re.search(r"primary\s+key\s*\(([^)]+)\)", c, re.I)
                if mt:
                    pk_cols.update(x.strip().strip('"\'`[] ').lower() for x in mt.group(1).split(","))
                elif inline:
                    pk_cols.add(inline.group(1).lower())
        if not has_pk:
            no_pk.append(name)
        # foreign keys: inline REFERENCES on a column, or a table-level FOREIGN KEY (cols)
        fk_cols = set()
        for c in clauses:
            if re.search(r"\breferences\b", c, re.I) and not re.match(r"foreign\s+key", c, re.I):
                col = re.match(r"[\"'`\[]?([A-Za-z_]\w*)", c)
                if col:
                    fk_cols.add(col.group(1).lower())
            mt = re.search(r"foreign\s+key\s*\(([^)]+)\)", c, re.I)
            if mt:
                fk_cols.update(x.strip().strip('"\'`[] ').lower() for x in mt.group(1).split(","))
        idx = indexed.get(name.lower(), set()) | pk_cols
        for col in sorted(fk_cols):
            if col not in idx:
                unindexed_fk.append((name, col))
        # repeating groups: col1, col2, col3 (same stem, trailing digit) -> denormalised
        stems = {}
        for c in clauses:
            cm = re.match(r"[\"'`\[]?([A-Za-z_]\w*?)_?(\d+)[\"'`\]]?\s", c)
            if cm:
                stems.setdefault(cm.group(1).lower(), set()).add(cm.group(2))
        for stem, nums in stems.items():
            if len(nums) >= 3:
                repeating.append((name, stem, len(nums)))

    verdict = ("SCHEMA RISK - table(s) with no primary key" if no_pk else
               "SOUND, with gaps" if (unindexed_fk or repeating) else "SOUND")
    if log:
        print("THE SCHEMA CREW - relational DDL review (zero model calls)")
        print("tables: %d  (%s)\n" % (len(tables), ", ".join(tables[:12]) or "none found"))
        print("--- primary keys (a row needs an identity) ---")
        if no_pk:
            for t in no_pk:
                print("  [FAIL] %s has no PRIMARY KEY" % t)
        else:
            print("  [ok]   every table declares a primary key")
        print("\n--- foreign-key indexing (an unindexed FK scans on every join/cascade) ---")
        if unindexed_fk:
            for t, c in unindexed_fk:
                print("  [flag] %s.%s is a foreign key with no index" % (t, c))
        else:
            print("  [ok]   every foreign key is indexed (or there are none)")
        print("\n--- denormalisation smell ---")
        for t, stem, n in repeating:
            print("  [flag] %s has a repeating group %s1..%s%d - consider a child table" % (t, stem, stem, n))
        if not repeating:
            print("  [ok]   no obvious repeating-group columns")
        print("\n--- not checked (and not a pass) ---")
        print("  - query plans, selectivity, and whether an index is actually used (EXPLAIN)")
        print("  - data types, constraints, cascade correctness, and migration safety")
        print("  - access patterns - the right schema depends on how it is read, which this cannot see")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Structure only. The right design depends on real queries; route to a DBA / EXPLAIN.")
    return {"verdict": verdict, "tables": tables, "no_pk": no_pk,
            "unindexed_fk": unindexed_fk, "repeating": repeating}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos or not os.path.isfile(pos[0]):
        print("schema: need a path to a .sql DDL file", file=sys.stderr)
        return 2
    sql = open(pos[0], encoding="utf-8-sig", errors="replace").read()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(sql, log=None)
        return _emit.emit("schema", rep, 1 if rep["verdict"].startswith("SCHEMA RISK") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(sql, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(sql)
    return 1 if rep["verdict"].startswith("SCHEMA RISK") else 0


if __name__ == "__main__":
    sys.exit(main())

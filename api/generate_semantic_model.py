import os
import json
import re
import pandas as pd
from api.llm_router import call_llm

def _looks_like_dates(values) -> str | None:
    """Sniffs string samples for date/datetime content.

    Returns 'datetime' (has a time component), 'date' (dates only), or None.
    Conservative on purpose: needs digits + separators/month names in EVERY
    sample and >=80% pandas-parseable, so IDs like 'SO-123' stay strings.
    """
    vals = [str(v) for v in values if pd.notna(v) and str(v).strip() != ""]
    if len(vals) < 2:
        return None
    if not all(re.search(r"\d", v) for v in vals):
        return None
    if not all(re.search(r"[-/]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec",
                         v, re.IGNORECASE) for v in vals):
        return None
    try:
        parsed = pd.to_datetime(pd.Series(vals), errors="coerce", format="mixed")
    except Exception:
        return None
    if parsed.notna().mean() < 0.8:
        return None
    has_time = any(re.search(r"\d{1,2}:\d{2}", v) for v in vals)
    return "datetime" if has_time else "date"

def list_folder_files(folder_path: str, max_files: int = 300) -> dict:
    """Lists files in a local folder (recursive). Read-only: never modifies anything.

    Returns a compact dict with total counts, per-extension counts, and file names,
    suitable for answering inspection questions like 'how many sales Excel files
    are in this folder?' without building anything.
    """
    if not folder_path or not os.path.exists(folder_path):
        return {"success": False, "folder": folder_path or "",
                "error": f"Folder not found: {folder_path}"}
    if not os.path.isdir(folder_path):
        return {"success": False, "folder": folder_path,
                "error": f"Not a folder: {folder_path}"}

    files = []
    for root, _, names in os.walk(folder_path):
        for name in sorted(names):
            full = os.path.join(root, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = -1
            files.append({
                "name": name,
                "relative_path": os.path.relpath(full, folder_path),
                "extension": os.path.splitext(name)[1].lower(),
                "size_bytes": size,
            })

    total = len(files)
    by_ext = {}
    for f in files:
        by_ext[f["extension"] or "(no extension)"] = by_ext.get(f["extension"] or "(no extension)", 0) + 1

    shown = files[:max_files]
    return {
        "success": True,
        "folder": folder_path,
        "total_files": total,
        "counts_by_extension": by_ext,
        "files": [{"name": f["name"], "extension": f["extension"],
                   "size_bytes": f["size_bytes"]} for f in shown],
        "truncated": total > max_files,
    }

def _sniff_csv_delimiter(file_path: str) -> str:
    """Sniffs a CSV file's delimiter from its first bytes. Defaults to comma."""
    import csv
    try:
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            sample = f.read(8192)
        if not sample:
            return ","
        dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|'])
        if dialect.delimiter in (',', ';', '\t', '|'):
            return dialect.delimiter
    except Exception:
        pass
    return ","


def _read_table_columns(file_path: str) -> list:
    """Reads the header row of a CSV/Excel file and returns [{name, dataType}]."""
    lower = file_path.lower()
    if lower.endswith('.xlsx') or lower.endswith('.xls'):
        df = pd.read_excel(file_path, nrows=50)
    else:
        sep = _sniff_csv_delimiter(file_path)
        try:
            df = pd.read_csv(file_path, nrows=50, encoding='utf-8-sig', sep=sep)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, nrows=50, encoding='cp1252', sep=sep)

    columns = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        # Map pandas dtypes to simple types
        if 'int' in dtype:
            simple_type = 'integer'
        elif 'float' in dtype:
            simple_type = 'decimal'
        elif 'bool' in dtype:
            simple_type = 'boolean'
        elif 'datetime' in dtype:
            simple_type = 'datetime'
        elif 'object' in dtype or 'str' in dtype:
            # CSVs store dates as plain strings — sniff them so date
            # columns don't end up as text in the model.
            simple_type = _looks_like_dates(df[col].tolist()) or 'string'
        else:
            simple_type = 'string'
        columns.append({"name": col, "dataType": simple_type})
    return columns


def read_file_headers(file_paths: list) -> dict:
    """Reads the column headers of specific CSV/Excel files. Read-only.

    Use this when you need the schema of loose files on disk (e.g. before
    proposing a table that combines several files) — the files do not need
    to be in the Power BI model yet.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    results = []
    for fp in (file_paths or []):
        if not fp or not os.path.exists(fp):
            results.append({"file": fp, "success": False,
                            "error": f"File not found: {fp}"})
            continue
        try:
            cols = _read_table_columns(fp)
            entry = {"file": fp, "success": True, "columns": cols}
            odd = sorted({c["name"] for c in cols
                          if isinstance(c, dict) and c.get("name") != c.get("name", "").strip()})
            if odd:
                entry["warnings"] = [
                    "These headers contain leading/trailing whitespace and must be "
                    "referenced with their EXACT names in M-code: " + ", ".join(repr(o) for o in odd)]
            lower = fp.lower()
            if not (lower.endswith('.xlsx') or lower.endswith('.xls')):
                # Tell the agent the real delimiter so the generated M-code
                # reads the file correctly (e.g. [Delimiter=";"] vs ",").
                entry["delimiter"] = _sniff_csv_delimiter(fp)
            results.append(entry)
        except Exception as e:
            results.append({"file": fp, "success": False, "error": str(e)})
    return {"success": True, "files": results}


# Valid Power Query M primitive/structure type identifiers. Anything else in a
# `type X` position (e.g. `type integer`, `type string`) crashes evaluation
# with "The type identifier is invalid" — the LLM often leaks TOM/SQL names in.
_VALID_M_TYPES = {
    "none", "null", "logical", "number", "time", "date", "datetime",
    "datetimezone", "duration", "text", "binary", "type", "function",
    "table", "list", "record", "any", "anynonnull",
}

# TOM/SQL/pandas-ish names the LLM emits -> valid M identifiers.
_M_TYPE_ALIASES = {
    "integer": "number", "int": "number", "int64": "number",
    "bigint": "number", "smallint": "number",
    "double": "number", "float": "number", "real": "number",
    "numeric": "number", "money": "number", "decimal": "number",
    "string": "text", "text": "text", "str": "text", "char": "text",
    "varchar": "text", "nvarchar": "text",
    "boolean": "logical", "bool": "logical", "bit": "logical",
    "datetime": "datetime", "date": "date", "time": "time",
    "datetimezone": "datetimezone", "timestamp": "datetime",
    "binary": "binary", "bytes": "binary", "duration": "duration",
}


# TOM column types -> Power Query M type identifiers for Changed Type steps.
_TOM_TO_M_TYPE = {
    "string": "text",
    "int64": "number",
    "double": "number",
    "decimal": "number",
    "datetime": "datetime",
    "date": "date",
    "boolean": "logical",
    "binary": "binary",
}


def ensure_changed_type_step(mexpr: str, columns: list) -> str:
    """Appends a Changed Type step to M-code that lacks one.

    TOM column metadata alone leaves every Power Query column as text — the
    types only take effect when Table.TransformColumnTypes runs inside the
    M-code. Derives M types from the TOM dataTypes. Runs at proposal time
    and again at accept time via normalize. Leaves M-code that already has
    a TransformColumnTypes step (or has no usable columns) untouched.
    """
    import re
    if not isinstance(mexpr, str) or "Table.TransformColumnTypes" in mexpr:
        return mexpr
    pairs = []
    for c in (columns or []):
        if not isinstance(c, dict) or not c.get("name"):
            continue
        mtype = _TOM_TO_M_TYPE.get(str(c.get("dataType", "")).strip().lower(), "")
        if mtype:
            pairs.append("{" + json.dumps(c["name"]) + ", type " + mtype + "}")
    if not pairs:
        return mexpr
    m = re.search(r"(?m)^(\s*)in\s+(\S+)\s*$", mexpr)
    if m:
        indent, last = m.group(1), m.group(2)
    else:
        # Power BI's own shape puts the final step on the line after `in`.
        m = re.search(r"(?m)^(\s*)in\s*\n\s*(\S+)\s*$", mexpr)
        if m:
            indent, last = m.group(1), m.group(2)
        elif "\n" not in mexpr:
            # Single-line shape: let <bindings> in <last>.
            m = re.search(r"^(let\b.*)\bin\s+(\S+)\s*$", mexpr)
            if not m:
                return mexpr
            prefix, last = m.group(1), m.group(2)
            step = '#"Changed Type"'
            if step in mexpr:
                step = '#"Changed Type 1"'
            pairs_s = ", ".join(pairs)
            return (prefix + ", " + step + " = Table.TransformColumnTypes("
                    + last + ", {" + pairs_s + "}) in " + step)
        else:
            return mexpr
    step = '#"Changed Type"'
    if step in mexpr:
        step = '#"Changed Type 1"'
    changed = indent + step + " = Table.TransformColumnTypes(" + last + ", {\n"
    changed += ",\n".join(indent + "    " + p for p in pairs)
    changed += "\n" + indent + "})"
    new_tail = indent + "in\n" + indent + "    " + step
    return mexpr[:m.start()] + changed + "\n" + new_tail + "\n"


def _split_top_level(text: str) -> list:
    """Splits on top-level commas, respecting nested (){}[] and M strings
    (double-quote escaped as "")."""
    parts, depth, cur, in_str, i = [], 0, [], False, 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    cur.append('""')
                    i += 2
                    continue
                in_str = False
            cur.append(ch)
            i += 1
            continue
        if ch == '"':
            in_str = True
            cur.append(ch)
            i += 1
            continue
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append(''.join(cur))
    return parts




def count_file_reads_and_promotes(mexpr: str) -> tuple:
    """Counts file reads vs PromoteHeaders calls in M-code.

    Returns (reads, promotes). A combine that reads N files but promotes
    fewer than N times stacks raw header rows as data.
    """
    import re
    if not isinstance(mexpr, str):
        return (0, 0)
    reads = len(re.findall(r"Csv\.Document\s*\(|Excel\.Workbook\s*\(", mexpr))
    promotes = len(re.findall(r"Table\.PromoteHeaders\s*\(", mexpr))
    return (reads, promotes)


def heal_m_single_quotes(mexpr: str) -> str:
    """Rewrites single-quoted literals in file-read positions to M strings.

    Power Query M has no single-quoted strings — File.Contents('...') or
    [Delimiter='...'] is a parse error ('Token Literal expected'). The LLM
    leaks DAX-style quoting in, so fix the unambiguous positions:
    File.Contents('p') -> File.Contents("p"), Delimiter='X' -> Delimiter="X",
    and a quoted Encoding='1252' -> Encoding=1252 (numbers are bare in M).
    Runs at proposal time and again at accept time via normalize.
    """
    import re
    if not isinstance(mexpr, str):
        return mexpr
    out = mexpr
    if "File.Contents" in out:
        out = re.sub(r"File\.Contents\(\s*'((?:[^'\\]|\\.)*)'\s*\)",
                     lambda m: 'File.Contents("' + m.group(1) + '")', out)
    if "Delimiter" in out:
        out = re.sub(r"Delimiter\s*=\s*'([^']*)'",
                     lambda m: 'Delimiter="' + m.group(1) + '"', out)
    if "Encoding" in out:
        def _fix_enc(m):
            v = m.group(1)
            return "Encoding=" + v if re.fullmatch(r"\d+", v) else m.group(0)
        out = re.sub(r"Encoding\s*=\s*'([^']*)'", _fix_enc, out)
    if out != mexpr:
        print("[heal] M single-quoted literal(s) rewritten with double quotes.")
    return out


def find_missing_source_files(mexpr: str) -> list:
    """Returns absolute File.Contents paths from M-code missing on this machine.

    A combined table whose M-code points at files that do not exist can never
    refresh. Web URLs and relative paths are skipped (cannot be resolved
    reliably here); only absolute local paths are checked.
    """
    import re
    missing = []
    if not isinstance(mexpr, str) or "File.Contents" not in mexpr:
        return missing
    for m in re.finditer(r'File\.Contents\(\s*"((?:[^"\\]|\\.)*)"\s*\)', mexpr):
        local = m.group(1).replace("\\\\", "\\")
        if not os.path.isabs(local):
            continue
        if not os.path.exists(local) and local not in missing:
            missing.append(local)
    return missing


def repair_transformcolumntypes_shape(mexpr: str) -> str:
    """Repairs flattened Table.TransformColumnTypes calls.

    Correct shape: TransformColumnTypes(table, {{col, type}, ...}).
    The LLM sometimes emits (table, {col, type}, {col, type}, ...) — one arg
    per pair — which fails at refresh with 'N arguments were passed to a
    function which expects between 2 and 3'. Rewraps such calls. Leaves
    correct calls (and anything unrecognized) untouched.
    """
    import re
    if not isinstance(mexpr, str) or "Table.TransformColumnTypes" not in mexpr:
        return mexpr

    out = mexpr
    # iterate matches back-to-front so splicing never invalidates offsets
    matches = list(re.finditer(r"Table\.TransformColumnTypes\s*\(", out))
    for m in reversed(matches):
        open_idx = m.end() - 1
        depth, in_str, i = 0, False, open_idx
        while i < len(out):
            ch = out[i]
            if in_str:
                if ch == '"':
                    if i + 1 < len(out) and out[i + 1] == '"':
                        i += 2
                        continue
                    in_str = False
                i += 1
                continue
            if ch == '"':
                in_str = True
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if i >= len(out):
            continue  # unbalanced — leave alone
        inner = out[open_idx + 1:i]
        parts = [p.strip() for p in _split_top_level(inner)]
        if len(parts) < 3:
            continue  # 1-2 args: either fine or unfixable
        tail = []
        if re.fullmatch(r"\d+", parts[-1]):
            tail = [parts[-1]]  # MissingField enum preserved
            parts = parts[:-1]
        if len(parts) < 3 or not all(p.startswith("{") for p in parts[1:]):
            continue
        fixed = ("Table.TransformColumnTypes(" + parts[0] + ", {"
                 + ", ".join(parts[1:]) + "}"
                 + (", " + tail[0] if tail else "") + ")")
        print(f"[heal] TransformColumnTypes flattened call rewrapped "
              f"({len(parts) - 1} pairs).")
        out = out[:m.start()] + fixed + out[i + 1:]
    return out


def _match_braces(text: str, open_idx: int) -> int | None:
    """Returns the index of the '}' matching the '{' at open_idx."""
    depth, in_str, i = 0, False, open_idx
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def heal_missing_promote_headers(mexpr: str) -> str:
    """Wraps raw CSV reads inside Table.Combine({...}) with PromoteHeaders.

    Csv.Document returns Column1..ColumnN until its header row is promoted.
    Without this, a later Table.TransformColumnTypes(..., {{"OrderDate", ...}})
    fails at refresh with "The column 'OrderDate' of the table wasn't found."
    Only direct Csv.Document items inside a Table.Combine list are wrapped;
    let-bound reads and items already wrapped are left alone.
    """
    if not isinstance(mexpr, str):
        return mexpr
    if "Table.Combine" not in mexpr or "Csv.Document" not in mexpr:
        return mexpr

    reads, promotes = count_file_reads_and_promotes(mexpr)
    if reads == 0 or promotes >= reads:
        return mexpr

    out = mexpr
    inserted = 0
    for m in reversed(list(re.finditer(r"Table\.Combine\s*\(\s*\{", out))):
        open_idx = out.find("{", m.start())
        close_idx = _match_braces(out, open_idx)
        if close_idx is None:
            continue
        inner = out[open_idx + 1:close_idx]
        parts = _split_top_level(inner)
        new_parts = []
        for part in parts:
            stripped = part.strip()
            if "Csv.Document" in stripped and "Table.PromoteHeaders" not in stripped:
                lead = part[:len(part) - len(part.lstrip())]
                trail = part[len(part.rstrip()):]
                new_parts.append(
                    lead + "Table.PromoteHeaders(" + stripped + ")" + trail)
                inserted += 1
            else:
                new_parts.append(part)
        if inserted:
            out = out[:open_idx + 1] + ",".join(new_parts) + out[close_idx:]

    if inserted:
        print(f"[heal] PromoteHeaders inserted for {inserted} raw CSV "
              f"read(s) inside Table.Combine.")
    return out


def heal_redundant_promote_headers(mexpr: str) -> str:
    """Removes redundant Table.PromoteHeaders calls on already-promoted Table.Combine outputs.

    When combining multiple CSVs/Excels that are each individually promoted inside
    Table.Combine({...}), a subsequent Table.PromoteHeaders(Source) promotes the first
    data row into column headers (e.g. '2020-01-01' becomes a column name), breaking
    column references in Table.TransformColumnTypes.
    """
    if not isinstance(mexpr, str) or "Table.Combine" not in mexpr or "Table.PromoteHeaders" not in mexpr:
        return mexpr

    combine_match = re.search(r"([#\w\.\"]+)\s*=\s*(Table\.Combine\s*\(\s*\{.*?\}(?:\s*,\s*null)?\s*\))", mexpr, re.DOTALL)
    if not combine_match:
        return mexpr

    combine_var = combine_match.group(1).strip()
    combine_body = combine_match.group(2)
    if "Table.PromoteHeaders" not in combine_body:
        return mexpr

    pattern = (
        r"(?m)^([ \t]*)([#\w\.\"]+)\s*=\s*Table\.PromoteHeaders\s*\(\s*"
        + re.escape(combine_var)
        + r"(?:\s*,[^\)]*)?\)\s*(,?)\s*$"
    )
    prom_match = re.search(pattern, mexpr)
    if not prom_match:
        return mexpr

    prom_var = prom_match.group(2).strip()
    trailing_comma = prom_match.group(3)

    start, end = prom_match.span()
    before = mexpr[:start]
    after = mexpr[end:]
    if after.startswith("\r\n"):
        after = after[2:]
    elif after.startswith("\n"):
        after = after[1:]

    if not trailing_comma:
        before = re.sub(r",\s*$", "", before.rstrip()) + "\n"

    new_expr = before + after
    if prom_var.startswith('#"') and prom_var.endswith('"'):
        new_expr = new_expr.replace(prom_var, combine_var)
    else:
        new_expr = re.sub(r"\b" + re.escape(prom_var) + r"\b", combine_var, new_expr)

    print(f"[heal] Removed redundant Table.PromoteHeaders on already-promoted '{combine_var}' (bypassed '{prom_var}').")
    return new_expr


def _extract_combine_refs(table_refs_str: str) -> list:
    """Extracts real table identifiers from a Table.Combine{...} item list.

    Returns bare identifiers and #-"quoted" names, skipping inline
    expressions (Csv.Document(...), delimiters) and file paths.
    """
    import re
    refs = []
    for _m in re.finditer(r'#\"([^\"]+)\"', table_refs_str):
        _cand = _m.group(1)
        if _cand and not any(_ch in _cand for _ch in ("\\", "/", ":")):
            refs.append(_cand)
    bare_scan = re.sub(r'"[^"]*"', "", table_refs_str)
    bare_scan = re.sub(r"'[^']*'", "", bare_scan)
    for _tok in re.split(r'[,\s]+', bare_scan):
        _t = _tok.strip().strip("'")
        if _t and re.fullmatch(r'[A-Za-z_]\w*', _t):
            refs.append(_t)
    return refs


def heal_table_combine_refs(mexpr: str) -> str:
    """Rewrites bare string literals inside Table.Combine({...}) as identifiers.

    Table.Combine expects tables, but the LLM often emits display names as
    plain text ("Sales Data 2020"), which fails at refresh with 'cannot
    convert the value ... to type Table'. A bare string there is never valid,
    so "Name" becomes #"Name". File paths (containing \\, / or :) are left
    alone — those need Csv.Document reads, flagged separately at validation.
    """
    import re
    if not isinstance(mexpr, str) or "Table.Combine" not in mexpr:
        return mexpr

    def _fix_block(match):
        inner = match.group(1)
        # Only whole items that are a single quoted string can be table-name
        # mistakes (e.g. {"Sales Data"}). Strings nested inside function calls
        # (Csv.Document paths, Delimiter=",") are left strictly alone.
        fixed_items = []
        n = 0
        for _part in _split_top_level(inner):
            _s = _part.strip()
            _m2 = re.fullmatch(r'"([^"]*)"', _s)
            if _m2 and _m2.group(1) and not any(
                    ch in _m2.group(1) for ch in ("\\", "/", ":")):
                print(f"[heal] Table.Combine: rewrote bare \"{_m2.group(1)}\" as # identifier.")
                fixed_items.append('#"' + _m2.group(1) + '"')
                n += 1
            else:
                fixed_items.append(_part)
        # NOTE: the outer regex consumes through the item-list "}" but NOT the
        # Combine closing ")", so the rebuild must not add one.
        return "Table.Combine({" + ",".join(fixed_items) + "}"

    return re.sub(r"Table\.Combine\s*\(\s*\{([^}]*)\}", _fix_block, mexpr)


async def validate_combine_sources(session, current_messages, mexpr):
    """Checks Table.Combine references against let-bound steps and the model.

    Returns an error string when a referenced table exists neither as a step
    in the M-code nor as a model table (typical cause: loose file names used
    as if they were tables), else None.
    """
    import re
    import json
    m = re.search(r"Table\.Combine\s*\(\s*\{([^}]*)\}", mexpr or "")
    if not m:
        return None
    refs = _extract_combine_refs(m.group(1))
    if not refs:
        return None
    letbound = set()

    def _add_letbound(name):
        if name.startswith('#"') and name.endswith('"'):
            name = name[2:-1]
        letbound.add(name.replace(" ", "").lower())

    # let-bound step names (line starts, after `let`, or comma-separated).
    for lm in re.finditer(r'(?m)(?:^|let|,)\s*(#"[^"]+"|[A-Za-z_]\w*)\s*=', mexpr):
        _add_letbound(lm.group(1))
    needed = [r for r in refs if r.replace(" ", "").lower() not in letbound]
    if not needed:
        return None
    known = {}
    for msg in (current_messages or []):
        try:
            if isinstance(msg, dict) and msg.get("role") == "tool" and msg.get("name") == "table_operations":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    data = json.loads(content)
                    results = data.get("results", data.get("data", []))
                    if isinstance(results, list):
                        for res in results:
                            d = res.get("data", res) if isinstance(res, dict) else res
                            if isinstance(d, dict) and d.get("name"):
                                known[str(d["name"])] = str(d["name"])
        except Exception:
            pass
    if session is not None:
        try:
            res = await session.call_tool("table_operations", {"request": {"operation": "List"}})
            text = "".join(getattr(c, "text", "") for c in res.content)
            data = json.loads(text) if text else {}
            for t in data.get("data", data.get("results", [])):
                dd = t.get("data", t) if isinstance(t, dict) else t
                if isinstance(dd, dict) and dd.get("name"):
                    known[str(dd["name"])] = str(dd["name"])
        except Exception:
            pass
    missing, hints = [], []
    for r in needed:
        if r in known:
            continue
        ci = [k for k in known if k.replace(" ", "").lower() == r.replace(" ", "").lower()]
        if ci:
            hints.append(f"did you mean '{ci[0]}'?")
        else:
            missing.append(r)
    if not missing and not hints:
        return None
    sample = sorted(known)[:12]
    known_txt = ("Known model tables include: " + ", ".join(sample) + ". ") if sample else ""
    problems = []
    if missing:
        problems.append("not in the model: " + ", ".join("'" + x + "'" for x in missing))
    problems.extend(hints)
    return ("ERROR: M-Code Table.Combine references table(s) " + "; ".join(problems) + ". "
            + known_txt +
            "Fix the names (references with spaces need hash-quote identifiers like #\"Sales Data\"), or - if these "
            "are loose files rather than model tables - read each file with "
            "Csv.Document(File.Contents(\"...\")) instead of referencing names.")


def heal_m_type_identifiers_in_mexpression(mexpr: str) -> str:
    """Rewrites invalid M type identifiers (e.g. `type integer`) to valid ones.

    Runs at proposal time and again at accept time via normalize.
    Identifiers already valid in M are left untouched, as is anything
    unrecognized (safer than guessing).
    """
    import re
    if not isinstance(mexpr, str) or "type " not in mexpr:
        return mexpr

    def _fix_one(match):
        name = match.group(1)
        lowered = name.lower()
        if lowered in _VALID_M_TYPES:
            return match.group(0)
        if lowered in _M_TYPE_ALIASES:
            fixed = _M_TYPE_ALIASES[lowered]
            print(f"[heal] M type auto-corrected: type {name} -> type {fixed}")
            return "type " + fixed
        return match.group(0)

    return re.sub(r"\btype\s+([A-Za-z_]\w*)", _fix_one, mexpr)


def heal_csv_delimiters_in_mexpression(mexpr: str) -> str:
    """Rewrites Csv.Document Delimiter options to match the real local files.

    The LLM often guesses the delimiter (e.g. ";"). A wrong or
    multi-character delimiter breaks Refresh in Power BI, so verify each
    File.Contents path that exists locally and fix mismatches. Runs both
    at proposal time and again at accept time via normalize.
    """
    import re
    if not isinstance(mexpr, str) or "Csv.Document" not in mexpr:
        return mexpr

    def _fix_one(match):
        raw_path, options = match.group(1), match.group(2)
        local_path = raw_path.replace("\\\\", "\\")
        if not os.path.exists(local_path):
            return match.group(0)
        dm = re.search(r'Delimiter\s*=\s*"([^"]*)"', options)
        if not dm:
            return match.group(0)
        claimed = dm.group(1)
        real = _sniff_csv_delimiter(local_path)
        if claimed == real and len(claimed) == 1:
            return match.group(0)
        fixed_options = options[:dm.start(1)] + real + options[dm.end(1):]
        print(f"[heal] Delimiter auto-corrected for {local_path}: {claimed!r} -> {real!r}")
        # NOTE: the regex consumes up to and including the options "]" but NOT
        # the Csv.Document closing ")", so the replacement must not add one.
        return 'Csv.Document(File.Contents("' + raw_path + '"),[' + fixed_options + ']'

    return re.sub(
        r'Csv\.Document\s*\(\s*File\.Contents\(\s*"((?:[^"\\]|\\.)*)"\s*\)\s*,\s*\[([^\]]*)\]',
        _fix_one, mexpr)


def get_csv_metadata(folder_path: str) -> dict:
    """Reads the first few lines of all CSV/Excel files in the folder to extract schema metadata."""
    if not os.path.exists(folder_path):
        raise ValueError(f"Folder not found: {folder_path}")

    metadata = {}
    seen_tables = set()

    for root, _, files in os.walk(folder_path):
        for filename in files:
            lower = filename.lower()
            is_csv = lower.endswith('.csv')
            is_excel = lower.endswith('.xlsx') or lower.endswith('.xls')
            if not (is_csv or is_excel):
                continue
                
            table_name = os.path.splitext(filename)[0]
            
            # If we've already processed a CSV with this name, just skip this duplicate
            if table_name.lower() in seen_tables:
                continue
                
            seen_tables.add(table_name.lower())
            file_path = os.path.join(root, filename)
        
            try:
                columns = _read_table_columns(file_path)
                    
                metadata[table_name] = {
                    "sourceFile": file_path,
                    "columns": columns
                }
            except Exception as e:
                print(f"Failed to read {filename}: {e}")
            
    return metadata

def generate_semantic_model(folder_path: str, settings: dict) -> dict:
    """Uses the LLM to generate a proposed Power BI semantic model schema from CSV files."""
    
    # 1. Read local CSV headers
    metadata = get_csv_metadata(folder_path)
    
    if not metadata:
        raise ValueError("No valid CSV or Excel files found in the specified folder.")
        
    csv_files_list = [t["sourceFile"] for t in metadata.values()]
    
    # 2. Construct LLM Prompt
    schema_text = json.dumps(metadata, indent=2)
    
    system_prompt = (
        "You are an expert Power BI data modeler. "
        "The user has provided a folder containing several raw CSV/Excel files. "
        "I will provide you with the extracted table names and column names from these files.\n\n"
        "Your job is to design a proposed Power BI semantic model (Star Schema). "
        "Identify Fact tables and Dimension tables based on common naming conventions and structures.\n"
        "IMPORTANT: You MUST completely strip out and remove any common prefixes like 'AdventureWorks ', 'Adventure Works ', or 'AdventureWorks' from the proposed table names to make them clean and short (e.g. 'Customer Lookup' instead of 'AdventureWorks Customer Lookup').\n"
        "Define relationships between the Fact and Dimension tables (usually Many-to-One).\n"
        "Also, propose a few essential DAX measures (like Total Sales, Row Count, etc.) if applicable.\n"
        "IMPORTANT: In your DAX measure expressions, if a table name contains spaces, it MUST be enclosed in single quotes (e.g., 'Sales Data'[Amount]). Always wrap table names in single quotes in DAX to be safe.\n\n"
        "You MUST return your response as a raw JSON object EXACTLY matching this structure, with NO markdown formatting, NO backticks, and NO additional text:\n"
        "{\n"
        '  "tables": [\n'
        '    {\n'
        '      "name": "TableName",\n'
        '      "type": "fact|dimension",\n'
        '      "sourceFile": "C:\\\\path\\\\to\\\\file.csv",\n'
        '      "columns": [{ "name": "ColName", "dataType": "string" }],\n'
        '      "measures": [{ "name": "Total XYZ", "expression": "SUM(\'TableName\'[ColName])" }]\n'
        '    }\n'
        '  ],\n'
        '  "relationships": [\n'
        '    {\n'
        '      "fromTable": "FactTable",\n'
        '      "fromColumn": "KeyCol",\n'
        '      "toTable": "DimTable",\n'
        '      "toColumn": "KeyCol",\n'
        '      "crossFilteringBehavior": "SingleDirection"\n'
        '    }\n'
        '  ]\n'
        "}\n"
    )
    
    user_prompt = f"Here is the schema extracted from the CSV files:\n\n{schema_text}\n\nPlease generate the proposed JSON model."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 3. Call LLM
    response = call_llm(messages, None, settings, stream=False)
    
    # Try to parse the response
    try:
        content = response.choices[0].message.content
        # Strip backticks if the model accidentally included them
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.startswith("```"):
            content = content.replace("```", "", 1)
        if content.endswith("```"):
            content = content[:-3]
            
        generated_schema = json.loads(content.strip())
        
        # Add the original detected files to the output so the UI can show them
        return {
            "schema": generated_schema,
            "csv_files": csv_files_list,
            "folder_path": folder_path
        }
    except Exception as e:
        raise ValueError(f"Failed to parse LLM response into JSON: {e}\n\nResponse was: {response.choices[0].message.content}")

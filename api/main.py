import os
import re
import json
import asyncio
import sys
import tempfile
import urllib.parse

# Suppress "RuntimeError: Event loop is closed" on Windows (bpo-45097)
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport
    _original_del = _ProactorBasePipeTransport.__del__
    def _silenced_del(self, _warn=None):
        try:
            _original_del(self)
        except RuntimeError:
            pass
    _ProactorBasePipeTransport.__del__ = _silenced_del
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from api.mcp_client import mcp_manager

# Load env but don't strictly require it initially, users can set via UI
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)

app = FastAPI(title="Power BI IDE API")

# Setup CORS for the React frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigManager:
    def __init__(self, path="config.json"):
        self.path = path

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return {}

    def save(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=4)

    def load_public(self):
        data = self.load()
        for key in ("databricks_token", "openai_api_key", "anthropic_api_key", "groq_api_key"):
            if key in data and data[key]:
                data[key] = "********"
        return data

config_mgr = ConfigManager()

def normalize_table_create_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize split or legacy table-create payloads into one valid MCP object per table.

    The real MCP expects a top-level 'mExpression' for M-based table creation. The LLM can
    sometimes emit malformed mixed payloads such as [{name: ...}, {mExpression: ...}] or
    extendedProperties containing a fake 'mExpression' property. These must be merged into a
    single valid table object before execution.
    """
    cleaned = json.loads(json.dumps(payload))
    request_block = cleaned.get("request", cleaned)
    definitions = request_block.get("definitions", []) if isinstance(request_block, dict) else []

    merged_by_name: Dict[str, Dict[str, Any]] = {}
    pending_name = None

    def extract_expression_from_extended_properties(obj: Dict[str, Any]) -> Optional[str]:
        props = obj.get("extendedProperties")
        if not isinstance(props, list):
            return None
        parts = []
        for item in props:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name == "mExpression":
                value = item.get("value")
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                elif isinstance(value, dict) and "expression" in value:
                    parts.append(value["expression"])
                elif isinstance(item, dict) and "expression" in item:
                    parts.append(item["expression"])
            elif name == "mExpressionContinuation":
                value = item.get("value")
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                elif isinstance(value, dict) and "expression" in value:
                    parts.append(value["expression"])
                elif isinstance(item, dict) and "expression" in item:
                    parts.append(item["expression"])
        if parts:
            return "".join(parts)
        # Fallback for legacy names
        for item in props:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name in {"source", "expression"}:
                value = item.get("value")
                if isinstance(value, str) and value.strip():
                    return value
                if isinstance(value, dict) and "expression" in value:
                    return value["expression"]
                if isinstance(item, dict) and "expression" in item:
                    return item["expression"]
        return None

    for item in definitions:
        if not isinstance(item, dict):
            continue

        fixed = dict(item)
        name = fixed.get("name")

        if name:
            pending_name = name
            if name not in merged_by_name:
                merged_by_name[name] = {}
            merged_by_name[name].update(fixed)
            # Also extract mExpression from extendedProperties if present on this named object
            if isinstance(fixed.get("extendedProperties"), list):
                expr = extract_expression_from_extended_properties(fixed)
                if expr:
                    merged_by_name[name]["mExpression"] = expr
                clean_props = []
                for prop in fixed["extendedProperties"]:
                    if not isinstance(prop, dict):
                        continue
                    prop_name = prop.get("name")
                    if prop_name in {"mExpression", "mExpressionContinuation", "source", "expression"}:
                        continue
                    clean_props.append(prop)
                merged_by_name[name]["extendedProperties"] = clean_props
            continue

        expr = fixed.get("mExpression")
        if not expr:
            expr = fixed.get("source")
        if not expr and isinstance(fixed.get("source"), dict):
            expr = fixed["source"].get("expression")
        if not expr:
            expr = extract_expression_from_extended_properties(fixed)

        if expr and pending_name:
            merged_by_name.setdefault(pending_name, {})
            merged_by_name[pending_name]["mExpression"] = expr
            # Carry the columns over too — otherwise the merged table looks
            # column-less and fails validation even though they were supplied.
            if fixed.get("columns") and not merged_by_name[pending_name].get("columns"):
                merged_by_name[pending_name]["columns"] = fixed["columns"]
            if isinstance(fixed.get("extendedProperties"), list):
                clean_props = []
                for prop in fixed["extendedProperties"]:
                    if not isinstance(prop, dict):
                        continue
                    if prop.get("name") in {"mExpression", "mExpressionContinuation", "source", "expression"}:
                        continue
                    clean_props.append(prop)
                merged_by_name[pending_name]["extendedProperties"] = clean_props
            continue

        if "partitions" in fixed and not fixed.get("mExpression"):
            partitions = fixed.get("partitions")
            if isinstance(partitions, list) and partitions:
                first_partition = partitions[0]
                if isinstance(first_partition, dict):
                    source = first_partition.get("source")
                    if isinstance(source, str):
                        expr = source
                    elif isinstance(source, dict) and "expression" in source:
                        expr = source["expression"]
                    if expr and pending_name:
                        merged_by_name.setdefault(pending_name, {})
                        merged_by_name[pending_name]["mExpression"] = expr
                        if fixed.get("columns") and not merged_by_name[pending_name].get("columns"):
                            merged_by_name[pending_name]["columns"] = fixed["columns"]
                        continue

        if "mExpression" in fixed and not pending_name:
            merged_by_name.setdefault("__unnamed__", {})
            merged_by_name["__unnamed__"]["mExpression"] = fixed["mExpression"]
            if fixed.get("columns") and not merged_by_name["__unnamed__"].get("columns"):
                merged_by_name["__unnamed__"]["columns"] = fixed["columns"]

    normalized_defs: List[Dict[str, Any]] = []
    for name, obj in merged_by_name.items():
        if name == "__unnamed__":
            normalized_defs.append(obj)
            continue
        fixed = dict(obj)
        fixed.pop("partitions", None)
        fixed.pop("source", None)
        fixed.pop("partitionName", None)
        props = fixed.get("extendedProperties")
        if isinstance(props, list):
            clean_props = []
            for prop in props:
                if not isinstance(prop, dict):
                    continue
                if prop.get("name") in {"mExpression", "mExpressionContinuation", "source", "expression"}:
                    continue
                clean_props.append(prop)
            fixed["extendedProperties"] = clean_props
        normalized_defs.append(fixed)

    if not normalized_defs:
        normalized_defs = [item for item in definitions if isinstance(item, dict)]

    # Minimal-shape policy for Create: the engine rejects invented decorative
    # fields (lineageTag names, bad prop types, ...), and each new one used to
    # surface as a fresh production failure. So for Create, definitions are
    # rebuilt keeping ONLY the fields known to be safe below — everything else
    # is dropped (and logged). This closes the whole class, not one field.
    _req_block = cleaned.get("request", {}) if isinstance(cleaned.get("request"), dict) else {}
    _create_op = str(_req_block.get("operation", cleaned.get("operation", ""))).lower() == "create"
    if _create_op:
        for _d in normalized_defs:
            if not isinstance(_d, dict):
                continue
            _dropped = [k for k in _d.keys() if k not in (
                "name", "mExpression", "description", "columns", "isHidden", "isPrivate")]
            _minimal = {}
            if isinstance(_d.get("name"), str) and _d.get("name", "").strip():
                _minimal["name"] = _d["name"]
            if isinstance(_d.get("mExpression"), str):
                _minimal["mExpression"] = _d["mExpression"]
            if isinstance(_d.get("description"), str):
                _minimal["description"] = _d["description"]
            for _bk in ("isHidden", "isPrivate"):
                if isinstance(_d.get(_bk), bool):
                    _minimal[_bk] = _d[_bk]
                elif _bk in _d:
                    _dropped.append(_bk + "(bad-type)")
            _new_cols = []
            for _c in (_d.get("columns") if isinstance(_d.get("columns"), list) else []):
                if not isinstance(_c, dict):
                    continue
                if not (isinstance(_c.get("name"), str) and _c.get("name", "").strip()):
                    _dropped.append("column-without-name")
                    continue
                _nc = {"name": _c["name"]}
                if isinstance(_c.get("dataType"), str):
                    _nc["dataType"] = _c["dataType"]
                for _sk in ("sourceColumn", "formatString", "description"):
                    if isinstance(_c.get(_sk), str):
                        _nc[_sk] = _c[_sk]
                _new_cols.append(_nc)
            if "columns" in _d or _new_cols:
                _minimal["columns"] = _new_cols
            if _dropped:
                print(f"[normalize] Dropped non-whitelisted Create fields from "
                      f"'{_minimal.get('name', '?')}': {sorted(set(_dropped))}")
            _d.clear()
            _d.update(_minimal)

    # Canonicalize column data types to the values the engine accepts
    # (Automatic, String, Int64, Double, DateTime, Decimal, Boolean, Binary,
    # Unknown, Variant). The LLM and file readers use loose names like
    # 'text'/'integer' which the engine rejects outright.
    _TYPE_MAP = {
        "automatic": "Automatic",
        "string": "String", "text": "String", "str": "String",
        "char": "String", "varchar": "String", "nvarchar": "String",
        "integer": "Int64", "int": "Int64", "int64": "Int64",
        "bigint": "Int64", "smallint": "Int64",
        "decimal": "Decimal",
        "double": "Double", "float": "Double", "real": "Double",
        "numeric": "Double", "money": "Double",
        "datetime": "DateTime", "date": "DateTime", "time": "DateTime",
        "timestamp": "DateTime",
        "boolean": "Boolean", "bool": "Boolean", "bit": "Boolean",
        "binary": "Binary", "bytes": "Binary",
        "unknown": "Unknown", "variant": "Variant",
    }
    for _d in normalized_defs:
        if not isinstance(_d, dict):
            continue
        # Lineage tags must be GUIDs or omitted — the LLM sometimes invents
        # display names here ("Sales Data"), which the engine rejects. Drop
        # anything that is not a valid GUID (null/omitted is accepted).
        for _lk in ("lineageTag", "sourceLineageTag"):
            _lv = _d.get(_lk)
            if _lv is None or _lk not in _d:
                continue
            if (not isinstance(_lv, str) or not re.match(
                    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", _lv.strip())):
                print(f"[normalize] Dropped invalid {_lk}: {_lv!r} (must be a GUID or omitted)")
                _d.pop(_lk, None)
        _cols = _d.get("columns")
        if isinstance(_cols, list):
            for _c in _cols:
                if not isinstance(_c, dict):
                    continue
                _t = _c.get("dataType")
                if isinstance(_t, str):
                    _c["dataType"] = _TYPE_MAP.get(_t.strip().lower(), "String")
        # Canonicalize extended property types: the engine only accepts
        # 'String' or 'Json' (capitalized). The LLM often emits 'string'.
        _props = _d.get("extendedProperties")
        if isinstance(_props, list):
            for _p in _props:
                if not isinstance(_p, dict):
                    continue
                _pt = _p.get("type")
                if isinstance(_pt, str):
                    _p["type"] = "Json" if _pt.strip().lower() == "json" else "String"

    for _d in normalized_defs:
        if isinstance(_d, dict) and isinstance(_d.get("mExpression"), str):
            from api.generate_semantic_model import heal_csv_delimiters_in_mexpression
            from api.generate_semantic_model import heal_m_single_quotes
            from api.generate_semantic_model import heal_m_type_identifiers_in_mexpression
            from api.generate_semantic_model import heal_table_combine_refs
            from api.generate_semantic_model import repair_transformcolumntypes_shape
            from api.generate_semantic_model import ensure_changed_type_step
            from api.generate_semantic_model import heal_missing_promote_headers
            from api.generate_semantic_model import heal_redundant_promote_headers
            _d["mExpression"] = heal_m_single_quotes(_d["mExpression"])
            _d["mExpression"] = heal_csv_delimiters_in_mexpression(_d["mExpression"])
            _d["mExpression"] = heal_table_combine_refs(_d["mExpression"])
            _d["mExpression"] = heal_missing_promote_headers(_d["mExpression"])
            _d["mExpression"] = heal_redundant_promote_headers(_d["mExpression"])
            _d["mExpression"] = heal_m_type_identifiers_in_mexpression(_d["mExpression"])
            _d["mExpression"] = repair_transformcolumntypes_shape(_d["mExpression"])
            _d["mExpression"] = ensure_changed_type_step(
                _d["mExpression"], _d.get("columns"))

    if "request" in cleaned:
        cleaned["request"]["definitions"] = normalized_defs
        return cleaned
    cleaned["definitions"] = normalized_defs
    return cleaned

_AFFIRMATIVE_EXACT = {
    "yes", "y", "yeah", "yep", "yup", "yea", "ya", "ywa", "sure",
    "ok", "okay", "k", "do it", "go ahead", "proceed", "confirmed",
    "please do", "please proceed", "sounds good", "go for it",
    "absolutely", "definitely", "lets do it", "let's do it", "agreed",
    "correct", "yes please", "yeah please", "sure thing", "of course",
}
_AFFIRMATIVE_START = {"yes", "yeah", "yep", "yup", "yea", "ya", "sure", "ok", "okay"}
_NEGATION_TOKENS = {"no", "nope", "not", "n't", "dont", "don't", "never",
                    "stop", "cancel", "cancelled", "canceled", "wait"}

def is_affirmative(text: str) -> bool:
    """True when a short user reply reads as confirmation (yes/sure/go ahead)."""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t).strip(" !.,;:")
    if not t:
        return False
    if t in _AFFIRMATIVE_EXACT:
        return True
    words = re.findall(r"[a-z']+", t)
    if not words:
        return False
    if any(w in _NEGATION_TOKENS for w in words):
        return False
    return len(words) <= 5 and words[0] in _AFFIRMATIVE_START

def maybe_inject_confirmation(history: list) -> bool:
    """If the newest user message affirms the assistant's previous question,
    append a clarification resolving it to an explicit instruction, so the
    agent acts instead of asking again. Returns True when injected."""
    if len(history) < 2:
        return False
    user_msg = history[-1]
    if not isinstance(user_msg, dict) or user_msg.get("role") != "user":
        return False
    if not is_affirmative(str(user_msg.get("content", ""))):
        return False
    last_asst = None
    for m in reversed(history[:-1]):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        content = (m.get("content") or "").strip()
        if content:
            last_asst = content
            break
    if not last_asst or not last_asst.rstrip().endswith("?"):
        return False
    history.append({
        "role": "user",
        "content": (
            "[Auto-clarified confirmation] My 'yes' above means: proceed with "
            "what you just proposed. Your question was: ..."
            + last_asst[-500:]
            + " Now perform the task — emit the required tool call(s)/proposal instead of asking again."
        ),
    })
    return True

class Settings(BaseModel):
    databricks_host: Optional[str] = None
    databricks_model: Optional[str] = None
    databricks_token: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    active_provider: Optional[str] = "databricks"

@app.get("/api/settings")
async def get_settings():
    return config_mgr.load_public()

@app.post("/api/settings")
async def save_settings(settings: Settings):
    existing = config_mgr.load()
    incoming = settings.model_dump(exclude_unset=True)
    for key, value in incoming.items():
        if key.endswith(("_token", "_api_key")) and (not value or value == "********"):
            continue
        existing[key] = value
    config_mgr.save(existing)
    return {"status": "success"}

try:
    import psutil
except ImportError:
    psutil = None

def find_pbi_instances():
    instances = []
    if not psutil:
        return instances
    try:
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if p.info['name'] and 'msmdsrv.exe' in p.info['name'].lower():
                    cmdline = p.info.get('cmdline', [])
                    workspace_dir = None
                    if '-s' in cmdline:
                        idx = cmdline.index('-s')
                        if idx + 1 < len(cmdline):
                            workspace_dir = cmdline[idx+1]
                    
                    port = None
                    if workspace_dir:
                        port_file = os.path.join(workspace_dir, 'msmdsrv.port.txt')
                        if os.path.exists(port_file):
                            try:
                                with open(port_file, 'r', encoding='utf-16le') as f:
                                    port = f.read().strip()
                            except:
                                with open(port_file, 'r') as f:
                                    port = f.read().strip()
                    
                    parent = p.parent()
                    dashboard_name = "Power BI Model"
                    if parent and 'pbidesktop' in parent.name().lower():
                        parent_cmd = parent.cmdline()
                        if len(parent_cmd) > 1:
                            for arg in parent_cmd[1:]:
                                if arg.lower().endswith('.pbix'):
                                    dashboard_name = os.path.basename(arg)
                                    break
                    
                    if port:
                        instances.append(f"{dashboard_name} (localhost:{port})")
            except Exception:
                pass
    except Exception:
        pass
    
    return instances

@app.get("/api/instances")
async def list_instances():
    try:
        instances = find_pbi_instances()
        if not instances:
            return {"status": "success", "data": ""}
        
        # Format it nicely for the frontend
        result_text = "Found instances:\\n"
        for i, inst in enumerate(instances):
            result_text += f"- {inst}\\n"
            
        return {"status": "success", "data": result_text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/connect")
async def connect_instance(payload: dict):
    instance_name = payload.get("instance_name")
    try:
        session = await mcp_manager.connect()
        result = await session.call_tool("connection_operations", {
            "request": {
                "operation": "Connect",
                "dataSource": instance_name
            }
        })
        result_text = "".join([c.text for c in result.content if hasattr(c, 'text')])
        return {"status": "success", "data": result_text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/model")
async def get_model():
    try:
        session = await mcp_manager.connect()
        result = await session.call_tool("model_operations", {"request": {"operation": "Get"}})
        result_text = "".join([c.text for c in result.content if hasattr(c, 'text')])
        return {"status": "success", "data": result_text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/schema")
async def get_schema():
    try:
        session = await mcp_manager.connect()
        
        # 1. Get Tables
        tables_res = await session.call_tool("table_operations", {"request": {"operation": "List"}})
        tables_text = "".join([c.text for c in tables_res.content if hasattr(c, 'text')])
        tables_data = json.loads(tables_text).get("data", [])
        
        # 2. Get Columns
        cols_res = await session.call_tool("column_operations", {"request": {"operation": "List"}})
        cols_text = "".join([c.text for c in cols_res.content if hasattr(c, 'text')])
        cols_data = json.loads(cols_text).get("data", [])
        
        # Map columns by table name
        cols_by_table = {item["tableName"]: item.get("columns", []) for item in cols_data if "tableName" in item}
        
        # 3. Get Measures for tables that have them
        schema = []
        for t in tables_data:
            t_name = t.get("name")
            t_measures = []
            if t.get("measureCount", 0) > 0:
                meas_res = await session.call_tool("measure_operations", {
                    "request": {
                        "operation": "List",
                        "filter": {"tableNames": [t_name]}
                    }
                })
                meas_text = "".join([c.text for c in meas_res.content if hasattr(c, 'text')])
                t_measures = json.loads(meas_text).get("data", [])
                
            schema.append({
                "name": t_name,
                "columns": cols_by_table.get(t_name, []),
                "measures": t_measures
            })
            
        # 4. Get Relationships
        rels_res = await session.call_tool("relationship_operations", {"request": {"operation": "List"}})
        rels_text = "".join([c.text for c in rels_res.content if hasattr(c, 'text')])
        rels_data = json.loads(rels_text).get("data", [])
            
        return {"status": "success", "data": {"tables": schema, "relationships": rels_data}}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/roles")
async def get_roles():
    try:
        session = await mcp_manager.connect()
        # First list all roles
        res = await session.call_tool("security_role_operations", {"request": {"operation": "List"}})
        text = "".join([c.text for c in res.content if hasattr(c, 'text')])
        data_json = json.loads(text)
        
        shallow_roles = []
        if "results" in data_json:
            for r in data_json["results"]:
                shallow_roles.append(r.get("data", r))
        elif "data" in data_json:
            shallow_roles = data_json["data"]
            
        full_roles = []
        for role in shallow_roles:
            role_name = role.get("name")
            if not role_name:
                continue
                
            # Fetch full details including tablePermissions for each role
            get_res = await session.call_tool("security_role_operations", {
                "request": {
                    "operation": "Get",
                    "references": [{"name": role_name}]
                }
            })
            get_text = "".join([c.text for c in get_res.content if hasattr(c, 'text')])
            get_data = json.loads(get_text)
            
            if "results" in get_data and len(get_data["results"]) > 0:
                full_roles.append(get_data["results"][0].get("data", get_data["results"][0]))
            elif "data" in get_data and isinstance(get_data["data"], list) and len(get_data["data"]) > 0:
                full_roles.append(get_data["data"][0])
            else:
                full_roles.append(role) # Fallback to shallow role

        return {"status": "success", "data": full_roles}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/measure/{table_name}/{measure_name}")
async def get_measure(table_name: str, measure_name: str):
    try:
        session = await mcp_manager.connect()
        res = await session.call_tool("measure_operations", {
            "request": {
                "operation": "Get",
                "references": [
                    {
                        "name": measure_name,
                        "tableName": table_name
                    }
                ]
            }
        })
        text = "".join([c.text for c in res.content if hasattr(c, 'text')])
        data = json.loads(text)
        if "results" in data and len(data["results"]) > 0:
            measure_data = data["results"][0].get("data", {})
            return {"status": "success", "data": measure_data}
        return {"status": "error", "message": "Measure not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/table/{table_name}/tmdl")
async def get_table_tmdl(table_name: str):
    try:
        session = await mcp_manager.connect()
        
        # We need to get the exact .tmdl file content. 
        # ExportTMDL directly to string is not fully supported by the MCP, 
        # so we export to a temp folder and read the file.
        with tempfile.TemporaryDirectory() as temp_dir:
            res = await session.call_tool("database_operations", {
                "request": {
                    "operation": "ExportToTmdlFolder",
                    "tmdlFolderPath": temp_dir
                }
            })
            
            # The file name is usually the table name with ".tmdl" extension.
            # E.g. "Calendar Lookup" -> "Calendar Lookup.tmdl"
            # However, some special characters might be encoded. We'll search for it.
            target_filename = f"{table_name}.tmdl"
            
            found_content = None
            all_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    all_files.append(os.path.join(root, file))
            
            # 1. Try exact filename match first (e.g. "Calendar Lookup.tmdl")
            for file_path in all_files:
                if os.path.basename(file_path) == target_filename:
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        found_content = f.read()
                    break
            
            # 2. Fallback: search for a file whose FIRST non-empty line is the table declaration
            #    Use strict regex so we don't match 'ref table' in model.tmdl
            if not found_content:
                table_header_re = re.compile(
                    r"^table\s+(?:'" + re.escape(table_name) + r"'|\"" + re.escape(table_name) + r"\"|" + re.escape(table_name) + r")\b",
                    re.IGNORECASE
                )
                for file_path in all_files:
                    if not file_path.endswith('.tmdl'):
                        continue
                    try:
                        with open(file_path, 'r', encoding='utf-8-sig') as f:
                            content = f.read()
                        first_line = content.lstrip().splitlines()[0] if content.strip() else ''
                        if table_header_re.match(first_line.strip()):
                            found_content = content
                            break
                    except Exception:
                        pass
            
            if found_content:
                return {"status": "success", "data": found_content}
                
            # Fallback if not found
            return {"status": "error", "message": f"TMDL file for table '{table_name}' not found in exported folder."}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# State management for proposals
@app.get("/api/table/{table_name}/mcode")
async def get_table_mcode(table_name: str):
    """Return the M-Code (Power Query) partition expression for a table."""
    try:
        session = await mcp_manager.connect()
        res = await session.call_tool("table_operations", {
            "request": {
                "operation": "Get",
                "references": [{"name": table_name}]
            }
        })
        text = "".join([c.text for c in res.content if hasattr(c, 'text')])
        data = json.loads(text)
        if "results" in data and len(data["results"]) > 0:
            table_data = data["results"][0].get("data", {})
            partitions = table_data.get("partitionDetails", [])
            if partitions:
                expression = partitions[0].get("expression", "")
                source_type = partitions[0].get("sourceType", "M")
                if expression:
                    return {"status": "success", "data": expression, "sourceType": source_type}
            return {"status": "error", "message": "No M-Code partition found for this table (it may be a DAX calculated table)."}
        return {"status": "error", "message": "Table not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class MeasureSaveRequest(BaseModel):
    expression: str

@app.post("/api/measure/{table_name}/{measure_name}")
async def save_measure(table_name: str, measure_name: str, req: MeasureSaveRequest):
    try:
        session = await mcp_manager.connect()
        res = await session.call_tool("measure_operations", {
            "request": {
                "operation": "Update",
                "definitions": [{
                    "name": measure_name,
                    "tableName": table_name,
                    "expression": req.expression
                }],
                "options": {"useTransaction": True}
            }
        })
        text = "".join([c.text for c in res.content if hasattr(c, 'text')])
        data = json.loads(text) if text else {}
        if data.get("success") is False or data.get("status") == "error" or data.get("errorMessage"):
            return {"status": "error", "message": data.get("message") or data.get("errorMessage") or text}
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class RoleSaveRequest(BaseModel):
    dax: str

@app.post("/api/role/{role_name}/{table_name}")
async def save_role_permission(role_name: str, table_name: str, req: RoleSaveRequest):
    try:
        session = await mcp_manager.connect()
        # Fetch existing role
        get_res = await session.call_tool("security_role_operations", {
            "request": {
                "operation": "Get",
                "references": [{"name": role_name}]
            }
        })
        get_text = "".join([c.text for c in get_res.content if hasattr(c, 'text')])
        get_data = json.loads(get_text)
        # We don't even need to fetch the existing role just to update one permission!
        # We can directly use UpdatePermissions.
        res = await session.call_tool("security_role_operations", {
            "request": {
                "operation": "UpdatePermissions",
                "permissionDefinitions": [{
                    "roleName": role_name,
                    "tableName": table_name,
                    "filterExpression": req.dax
                }],
                "options": {"useTransaction": True}
            }
        })
        text = "".join([c.text for c in res.content if hasattr(c, 'text')])
        data = json.loads(text) if text else {}
        if data.get("success") is False or data.get("status") == "error" or data.get("errorMessage"):
            return {"status": "error", "message": data.get("message") or data.get("errorMessage") or text}
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class TableSaveRequest(BaseModel):
    content: str
    type: str  # "tmdl" or "mcode"

@app.post("/api/table/{table_name}")
async def save_table(table_name: str, req: TableSaveRequest):
    try:
        if not table_name or table_name in {".", ".."} or "/" in table_name or "\\" in table_name:
            raise HTTPException(status_code=400, detail="Invalid table name")
        if req.type not in {"tmdl", "mcode"}:
            raise HTTPException(status_code=400, detail="Unsupported table content type")

        session = await mcp_manager.connect()
        if req.type == "tmdl":
            # For TMDL, we write to a temp directory and use ImportFromTmdlFolder
            with tempfile.TemporaryDirectory() as temp_dir:
                # First export current model to temp folder to get full structure
                await session.call_tool("database_operations", {
                    "request": {
                        "operation": "ExportToTmdlFolder",
                        "tmdlFolderPath": temp_dir
                    }
                })
                
                # Find and overwrite the specific table's TMDL file
                target_filename = f"{table_name}.tmdl"
                file_replaced = False
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file == target_filename:
                            with open(os.path.join(root, file), 'w', encoding='utf-8-sig') as f:
                                f.write(req.content)
                            file_replaced = True
                            break
                
                if not file_replaced:
                    # Create it in tables directory if it exists
                    tables_dir = os.path.join(temp_dir, "tables")
                    if not os.path.exists(tables_dir):
                        os.makedirs(tables_dir)
                    with open(os.path.join(tables_dir, target_filename), 'w', encoding='utf-8-sig') as f:
                        f.write(req.content)
                
                # Import back
                res = await session.call_tool("database_operations", {
                    "request": {
                        "operation": "ImportFromTmdlFolder",
                        "tmdlFolderPath": temp_dir
                    }
                })
                text = "".join([c.text for c in res.content if hasattr(c, 'text')])
                return {"status": "success", "data": text}
                
        elif req.type == "mcode":
            # For M-Code, we update the partition
            # First get the table to find the partition name
            res_get = await session.call_tool("table_operations", {
                "request": {
                    "operation": "Get",
                    "references": [{"name": table_name}]
                }
            })
            text_get = "".join([c.text for c in res_get.content if hasattr(c, 'text')])
            data_get = json.loads(text_get)
            
            if "results" in data_get and len(data_get["results"]) > 0:
                table_data = data_get["results"][0].get("data", {})
                partitions = table_data.get("partitionDetails", [])
                if partitions:
                    partition_name = partitions[0].get("name")
                    # Update partition. partition_operations expects Definitions
                    # (not a singular "partition" object); the old shape failed
                    # with "Missing required parameters for Update operation".
                    res = await session.call_tool("partition_operations", {
                        "request": {
                            "operation": "Update",
                            "definitions": [{
                                "name": partition_name,
                                "tableName": table_name,
                                "expression": req.content
                            }]
                        }
                    })
                    text = "".join([c.text for c in res.content if hasattr(c, 'text')])
                    data = json.loads(text) if text else {}
                    if data.get("success") is False:
                        return {"status": "error", "message": data.get("message") or text}
                    return {"status": "success", "data": data}
            
            return {"status": "error", "message": "Could not update M-Code: partition not found"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/model/refresh")
async def refresh_model():
    try:
        session = await mcp_manager.connect()
        # NOTE: database_operations has no Refresh op — model refresh lives here.
        res = await session.call_tool("model_operations", {
            "request": {
                "operation": "Refresh",
                "refreshType": "Full"
            }
        })
        text = "".join([c.text for c in res.content if hasattr(c, 'text')])
        return {"status": "success", "data": text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class PushModelRequest(BaseModel):
    model_schema: dict
    folder_path: str

@app.post("/api/generate/push")
async def push_generated_model(req: PushModelRequest):
    try:
        session = await asyncio.wait_for(mcp_manager.connect(), timeout=15.0)
        schema = req.model_schema
        
        # 1. Create Tables & Partitions
        table_definitions = []
        
        # Find primary keys based on the relationships (toTable -> toColumn)
        dim_pks = {}
        for rel in schema.get('relationships', []):
            t_table = rel.get('toTable')
            t_col = rel.get('toColumn')
            if t_table and t_col:
                dim_pks[t_table] = t_col
                
        for table in schema.get('tables', []):
            mcode_path = table.get("sourceFile", "").replace('"', '""')
            table_name = table.get("name")
            is_dim = table.get("type", "").lower() == "dimension"
            
            # Default encoding 1252 for Windows standard handling as discussed
            columns_count = len(table.get('columns', []))

            is_excel_source = mcode_path.lower().endswith('.xlsx') or mcode_path.lower().endswith('.xls')
            if is_excel_source:
                # Excel sources must be read with Excel.Workbook, not Csv.Document.
                # Source{0}[Data] picks the first worksheet regardless of its name.
                m_expression_str = (
                    'let\n'
                    f'    Source = Excel.Workbook(File.Contents("{mcode_path}"), null, true),\n'
                    '    FirstSheet = Source{0}[Data],\n'
                    '    Promoted = Table.PromoteHeaders(FirstSheet)'
                )
            else:
                m_expression_str = (
                    'let\n'
                    f'    Source = Csv.Document(File.Contents("{mcode_path}"),[Delimiter=",", Columns={columns_count}, Encoding=1252, QuoteStyle=QuoteStyle.Csv]),\n'
                    '    Promoted = Table.PromoteHeaders(Source)'
                )
            
            if is_dim:
                pk_col = dim_pks.get(table_name)
                if pk_col:
                    m_expression_str += f',\n    Filtered = Table.SelectRows(Promoted, each [{pk_col}] <> null and [{pk_col}] <> ""),\n'
                    m_expression_str += f'    Distinct = Table.Distinct(Filtered, {{"{pk_col}"}})\n'
                else:
                    m_expression_str += ',\n    Distinct = Table.Distinct(Promoted)\n'
                m_expression_str += 'in\n    Distinct'
            else:
                m_expression_str += '\nin\n    Promoted'
            
            columns = []
            for col in table.get('columns', []):
                dtype = col.get("dataType", "string").lower()
                # Map our simple types back to TOM types
                type_map = {
                    "integer": "int64",
                    "decimal": "double",
                    "datetime": "dateTime",
                    "boolean": "boolean",
                    "string": "string"
                }
                tom_type = type_map.get(dtype, "string")
                columns.append({
                    "name": col["name"],
                    "dataType": tom_type,
                    "sourceColumn": col["name"]
                })
                
            table_definitions.append({
                "name": table["name"],
                "mExpression": m_expression_str,
                "columns": columns
            })
            
        if table_definitions:
            res = await session.call_tool("table_operations", {
                "request": {
                    "operation": "Create",
                    "definitions": table_definitions,
                    "options": {"useTransaction": True}
                }
            })
            text = "".join([c.text for c in res.content if hasattr(c, 'text')])
            data = json.loads(text) if text else {}
            if data.get("success") is False:
                raise ValueError(f"Failed to create tables. MCP response: {json.dumps(data)}")

        # 2. Create Relationships
        rels = schema.get('relationships', [])
        if rels:
            # Check existing first (List needs no args; read both envelopes)
            existing_res = await session.call_tool("relationship_operations", {
                "request": {"operation": "List"}
            })
            ext_text = "".join([c.text for c in existing_res.content if hasattr(c, "text")])
            existing_rels = []
            try:
                ext_data = json.loads(ext_text)
                existing_rels = ext_data.get("data", ext_data.get("results", []))
            except:
                pass
                
            rel_definitions = []
            for r in rels:
                exists = False
                for e in existing_rels:
                    e_data = e.get("data", {})
                    if (e_data.get("fromTable") == r["fromTable"] and e_data.get("fromColumn") == r["fromColumn"] and
                        e_data.get("toTable") == r["toTable"] and e_data.get("toColumn") == r["toColumn"]):
                        exists = True
                        break
                if not exists:
                    rel_definitions.append({
                        "fromTable": r["fromTable"],
                        "fromColumn": r["fromColumn"],
                        "toTable": r["toTable"],
                        "toColumn": r["toColumn"],
                        "crossFilteringBehavior": r.get("crossFilteringBehavior", "SingleDirection")
                    })
            
            if rel_definitions:
                res = await session.call_tool("relationship_operations", {
                    "request": {
                        "operation": "Create",
                        "definitions": rel_definitions,
                        "options": {"useTransaction": True}
                    }
                })
                text = "".join([c.text for c in res.content if hasattr(c, 'text')])
                data = json.loads(text) if text else {}
                if data.get("success") is False:
                    raise ValueError(f"Failed to create relationships: {data.get('message') or data.get('errorMessage')}")

        # 3. Create Measures
        measure_definitions = []
        for table in schema.get('tables', []):
            for m in table.get('measures', []):
                measure_definitions.append({
                    "name": m["name"],
                    "tableName": table["name"],
                    "expression": m["expression"]
                })
                
        if measure_definitions:
            res = await session.call_tool("measure_operations", {
                "request": {
                    "operation": "Create",
                    "definitions": measure_definitions,
                    "options": {"useTransaction": True}
                }
            })
            text = "".join([c.text for c in res.content if hasattr(c, 'text')])
            data = json.loads(text) if text else {}
            if data.get("success") is False:
                raise ValueError(f"Failed to create measures: {data.get('message') or data.get('errorMessage')}")

        # Refresh the model to load data from the CSVs
        # NOTE: database_operations has no Refresh op — model refresh lives here.
        await session.call_tool("model_operations", {
            "request": {
                "operation": "Refresh",
                "refreshType": "Full"
            }
        })
        
        return {"status": "success", "message": f"Model pushed successfully with {len(table_definitions)} tables, {len(rels)} relationships, and {len(measure_definitions)} measures!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# State management for proposals
proposals = {}

async def get_live_column_index(session):
    tables_res = await session.call_tool("table_operations", {"request": {"operation": "List"}})
    columns_res = await session.call_tool("column_operations", {"request": {"operation": "List"}})

    tables_text = "".join(c.text for c in tables_res.content if hasattr(c, "text"))
    columns_text = "".join(c.text for c in columns_res.content if hasattr(c, "text"))
    tables_data = json.loads(tables_text) if tables_text else {}
    columns_data = json.loads(columns_text) if columns_text else {}

    table_names = {
        str(table.get("name")): str(table.get("name"))
        for table in tables_data.get("data", [])
        if isinstance(table, dict) and table.get("name")
    }
    columns_by_table = {}
    for table_columns in columns_data.get("data", []):
        if not isinstance(table_columns, dict) or not table_columns.get("tableName"):
            continue
        columns_by_table[str(table_columns["tableName"]).casefold()] = {
            str(column.get("name")).casefold(): str(column.get("name"))
            for column in table_columns.get("columns", [])
            if isinstance(column, dict) and column.get("name")
        }

    return table_names, columns_by_table

async def validate_relationship_definitions(session, definitions):
    table_names, columns_by_table = await get_live_column_index(session)
    tables_by_key = {name.casefold(): name for name in table_names}
    errors = []

    for index, definition in enumerate(definitions):
        if not isinstance(definition, dict):
            errors.append(f"Relationship {index + 1} is not a valid object")
            continue

        missing = []
        for table_key, column_key, side in (
            ("fromTable", "fromColumn", "from"),
            ("toTable", "toColumn", "to"),
        ):
            table_name = str(definition.get(table_key, ""))
            column_name = str(definition.get(column_key, ""))
            actual_table = tables_by_key.get(table_name.casefold())
            if not actual_table:
                missing.append(f"{side} table '{table_name}'")
                continue

            actual_columns = columns_by_table.get(actual_table.casefold(), {})
            if column_name.casefold() not in actual_columns:
                missing.append(f"{side} column '{column_name}' in table '{actual_table}'")

        if missing:
            relationship_name = definition.get("name") or (
                f"{definition.get('fromTable', '?')} to {definition.get('toTable', '?')}"
            )
            errors.append(f"{relationship_name}: {', '.join(missing)}")

        # Cardinalities must be explicit on both sides — the engine rejects
        # relationships without them with an opaque "invalid schema" error.
        # Convention: fromCardinality 'Many' on the fact side,
        # toCardinality 'One' on the dimension side.
        for card_key, side_name in (("fromCardinality", "from"), ("toCardinality", "to")):
            if not definition.get(card_key):
                errors.append(
                    f"{definition.get('fromTable', '?')} to {definition.get('toTable', '?')}: "
                    f"missing '{card_key}' — set fromCardinality 'Many' on the fact side and "
                    f"toCardinality 'One' on the dimension side explicitly"
                )

    return errors

def relationship_matches(existing, definition):
    relationship = existing.get("data", existing) if isinstance(existing, dict) else {}
    return all(
        relationship.get(existing_key) == definition.get(definition_key)
        for existing_key, definition_key in (
            ("fromTable", "fromTable"),
            ("fromColumn", "fromColumn"),
            ("toTable", "toTable"),
            ("toColumn", "toColumn"),
        )
    )

def relationship_matches_reversed(existing, definition):
    relationship = existing.get("data", existing) if isinstance(existing, dict) else {}
    return all(
        relationship.get(existing_key) == definition.get(definition_key)
        for existing_key, definition_key in (
            ("fromTable", "toTable"),
            ("fromColumn", "toColumn"),
            ("toTable", "fromTable"),
            ("toColumn", "fromColumn"),
        )
    )

async def split_existing_relationship_definitions(session, definitions):
    existing_res = await session.call_tool("relationship_operations", {
        "request": {"operation": "List"}
    })
    existing_text = "".join(c.text for c in existing_res.content if hasattr(c, "text"))
    existing_data = json.loads(existing_text) if existing_text else {}
    existing_relationships = existing_data.get("data", existing_data.get("results", []))
    if not isinstance(existing_relationships, list):
        existing_relationships = []

    remaining = []
    skipped = []
    for definition in definitions:
        if any(relationship_matches(existing, definition) for existing in existing_relationships):
            skipped.append(definition)
        else:
            remaining.append(definition)
    return remaining, skipped

def normalize_dax(expr: str) -> str:
    if not expr:
        return ""
    # Strip comments
    expr = re.sub(r'(--|//).*?(\n|$)', ' ', expr)
    expr = re.sub(r'/\*.*?\*/', ' ', expr, flags=re.DOTALL)
    # Strip all whitespace for canonical comparison
    return "".join(expr.split()).casefold()

def extract_measure_definitions(data) -> list:
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if not isinstance(data, dict):
        return []
    req = data.get("request", {}) if isinstance(data.get("request"), dict) else {}
    defs = req.get("definitions", []) or data.get("definitions", [])
    if isinstance(defs, list) and defs:
        return [d for d in defs if isinstance(d, dict)]
    name = req.get("name") or data.get("name")
    if name:
        return [{
            "name": name,
            "tableName": req.get("tableName") or data.get("tableName", ""),
            "expression": req.get("expression") or data.get("expression", "")
        }]
    return []

async def get_live_measures(session):
    try:
        tables_res = await session.call_tool("table_operations", {"request": {"operation": "List"}})
        tables_text = "".join(c.text for c in tables_res.content if hasattr(c, "text"))
        tables_data = json.loads(tables_text) if tables_text else {}
        tables_list = tables_data.get("data", tables_data.get("results", []))
        if not isinstance(tables_list, list):
            tables_list = []
    except Exception:
        tables_list = []

    measures = []
    for t in tables_list:
        if not isinstance(t, dict):
            continue
        t_name = t.get("name")
        if not t_name:
            continue
        # Only query tables that contain measures
        if t.get("measureCount", 0) > 0 or not tables_list:
            try:
                meas_res = await session.call_tool("measure_operations", {
                    "request": {
                        "operation": "List",
                        "filter": {"tableNames": [t_name]}
                    }
                })
                meas_text = "".join(c.text for c in meas_res.content if hasattr(c, "text"))
                meas_data = json.loads(meas_text) if meas_text else {}
                items = meas_data.get("data", meas_data.get("results", []))
                if isinstance(items, list):
                    for item in items:
                        m_info = item.get("data", item) if isinstance(item, dict) else {}
                        if m_info.get("name"):
                            m_info.setdefault("tableName", t_name)
                            measures.append(m_info)
            except Exception:
                pass
    return measures

async def validate_measure_creation(session, data):
    """
    Validates measure creation before proposing or applying.
    Returns (error_msg, notice_msg).
    - error_msg: Present if duplicate name exists (Hard Block).
    - notice_msg: Present if identical DAX expression exists under a different name (Smart Advisory).
    """
    definitions = extract_measure_definitions(data)
    if not definitions:
        return None, None
        
    try:
        existing_measures = await get_live_measures(session)
    except Exception:
        return None, None

    for defn in definitions:
        if not isinstance(defn, dict):
            continue
        proposed_name = str(defn.get("name", "")).strip()
        proposed_table = str(defn.get("tableName", "")).strip()
        proposed_dax = str(defn.get("expression", "")).strip()
        norm_proposed_dax = normalize_dax(proposed_dax)

        if not proposed_name:
            continue

        # 1. Hard Block: Duplicate Name
        for em in existing_measures:
            em_name = str(em.get("name", "")).strip()
            em_table = str(em.get("tableName", "")).strip()
            if em_name.casefold() == proposed_name.casefold():
                table_str = f" in table '{em_table}'" if em_table else ""
                return (
                    f"A measure named '{proposed_name}' already exists{table_str} in the model.\n\n"
                    f"Power BI does not allow duplicate measure names. "
                    f"Would you like me to update the existing measure instead, or choose a different name?",
                    None
                )

        # 2. Smart Advisory: Duplicate DAX expression under different name
        if norm_proposed_dax:
            for em in existing_measures:
                em_name = str(em.get("name", "")).strip()
                em_table = str(em.get("tableName", "")).strip()
                em_dax = normalize_dax(str(em.get("expression", "")))
                if em_dax and em_dax == norm_proposed_dax and em_name.casefold() != proposed_name.casefold():
                    table_str = f" in table '{em_table}'" if em_table else ""
                    return (
                        None,
                        f"An identical DAX expression already exists in measure '{em_name}'{table_str}. "
                        f"Please inform the user that '{em_name}' already calculates this exact formula, "
                        f"while confirming that you have proposed '{proposed_name}' with the same calculation."
                    )

    return None, None

from typing import List, Dict, Any

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    session_id: Optional[str] = None
    intelligence_mode: Optional[str] = "standard"

conversation_histories = {}

class QueryRequest(BaseModel):
    query: str

class RelationshipCreateRequest(BaseModel):
    fromTable: str
    fromColumn: str
    toTable: str
    toColumn: str
    fromCardinality: Optional[str] = None
    toCardinality: Optional[str] = None
    crossFilteringBehavior: str = "SingleDirection"

def normalize_dax_query(query: str) -> str:
    query = query.strip()
    if re.match(r"^(EVALUATE|DEFINE)\b", query, re.IGNORECASE):
        return query

    table_expression = re.match(
        r"^(SUMMARIZECOLUMNS|SUMMARIZE|FILTER|SELECTCOLUMNS|ADDCOLUMNS|VALUES|DISTINCT|"
        r"UNION|INTERSECT|EXCEPT|CROSSJOIN|TOPN|DATATABLE)\b|^\{",
        query,
        re.IGNORECASE
    )
    if table_expression:
        return f"EVALUATE\n{query}"

    return f'EVALUATE\nROW("Result", {query})'

@app.post("/api/query")
async def execute_dax_query(req: QueryRequest):
    if not req.query.strip():
        return {"status": "error", "message": "DAX query cannot be empty"}

    try:
        executed_query = normalize_dax_query(req.query)
        session = await asyncio.wait_for(mcp_manager.connect(), timeout=15.0)
        result = await asyncio.wait_for(session.call_tool("dax_query_operations", {
            "request": {
                "operation": "Execute",
                "query": executed_query,
                "getExecutionMetrics": True,
                "executionMetricsOnly": False
            }
        }), timeout=180.0)
        result_text = result.content[0].text if result.content else ""
        data = json.loads(result_text) if result_text else {}

        if data.get("success") is False or data.get("status") == "error":
            return {"status": "error", "message": data.get("message") or data.get("errorMessage") or result_text}

        result_data = data.get("data", {})
        rows = result_data.get("rows", []) if isinstance(result_data, dict) else []
        columns = list(rows[0].keys()) if rows else []
        return {
            "status": "success",
            "data": {
                "columns": columns,
                "rows": rows,
                "rowCount": len(rows),
                "executedQuery": executed_query
            }
        }
    except json.JSONDecodeError:
        return {"status": "error", "message": "The MCP returned an unreadable query result"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def auto_clean_table(session, table_name, column_name):
    # 1. Get the table's partition
    res_get = await session.call_tool("table_operations", {
        "request": {
            "operation": "Get",
            "references": [{"name": table_name}]
        }
    })
    text_get = "".join([c.text for c in res_get.content if hasattr(c, 'text')])
    data_get = json.loads(text_get)
    if not ("results" in data_get and len(data_get["results"]) > 0):
        return False
    table_data = data_get["results"][0].get("data", {})
    partitions = table_data.get("partitionDetails", [])
    if not partitions:
        return False
    partition_name = partitions[0].get("name")
    mcode = partitions[0].get("source", {}).get("expression") or partitions[0].get("expression")
    if not mcode:
        return False
    
    if "AutoDistinct" in mcode:
        return True # already cleaned
        
    # 2. Inject cleaning logic
    match = re.search(r'\sin\s+([#"a-zA-Z0-9_ ]+)\s*$', mcode, flags=re.MULTILINE)
    if not match:
        return False
    last_step = match.group(1).strip()
    new_steps = f',\n    AutoCleaned = Table.SelectRows({last_step}, each [{column_name}] <> null and [{column_name}] <> ""), \n    AutoDistinct = Table.Distinct(AutoCleaned, {{"{column_name}"}})\nin\n    AutoDistinct'
    new_mcode = mcode[:match.start()] + new_steps

    # 3. Update partition
    await session.call_tool("partition_operations", {
        "request": {
            "operation": "Update",
            "references": [{"name": partition_name, "tableName": table_name}],
            "partition": {"expression": new_mcode}
        }
    })
    
    # 4. Refresh the table
    await session.call_tool("model_operations", {
        "request": {
            "operation": "Refresh",
            "type": "Full",
            "objects": [{"table": table_name}]
        }
    })
    return True

@app.post("/api/relationship")
async def create_relationship(req: RelationshipCreateRequest):
    try:
        session = await asyncio.wait_for(mcp_manager.connect(), timeout=15.0)

        async def column_profile(table_name: str, column_name: str):
            table_literal = table_name.replace("'", "''")
            column_literal = column_name.replace("'", "''")
            profile_query = (
                'EVALUATE ROW("__rowCount", COUNTROWS(\'' + table_literal + '\'), '
                '"__distinctCount", DISTINCTCOUNT(\'' + table_literal + '\'[' + column_literal + ']))'
            )
            profile_result = await session.call_tool("dax_query_operations", {
                "request": {"operation": "Execute", "query": profile_query}
            })
            profile_text = profile_result.content[0].text if profile_result.content else ""
            profile_data = json.loads(profile_text) if profile_text else {}
            rows = profile_data.get("data", {}).get("rows", [])
            if not rows:
                return None
            row = rows[0]
            row_count = row.get("[__rowCount]", row.get("__rowCount"))
            distinct_count = row.get("[__distinctCount]", row.get("__distinctCount"))
            return int(row_count), int(distinct_count)

        from_profile = await column_profile(req.fromTable, req.fromColumn)
        to_profile = await column_profile(req.toTable, req.toColumn)
        if not from_profile or not to_profile:
            return {"status": "error", "message": "Could not inspect both relationship columns to infer cardinality."}

        from_unique = from_profile[0] == from_profile[1]
        to_unique = to_profile[0] == to_profile[1]
        if from_unique and not to_unique:
            from_table, from_column = req.toTable, req.toColumn
            to_table, to_column = req.fromTable, req.fromColumn
            from_cardinality, to_cardinality = "Many", "One"
        elif to_unique and not from_unique:
            from_table, from_column = req.fromTable, req.fromColumn
            to_table, to_column = req.toTable, req.toColumn
            from_cardinality, to_cardinality = "Many", "One"
        elif not from_unique and not to_unique:
            return {
                "status": "error",
                "message": "Neither selected column is unique, so Power BI cannot infer a one-to-many relationship. Select a lookup/key column on one side."
            }
        else:
            from_table, from_column = req.fromTable, req.fromColumn
            to_table, to_column = req.toTable, req.toColumn
            from_cardinality = "One" if from_unique else "Many"
            to_cardinality = "One" if to_unique else "Many"

        relationship_definition = {
            "fromTable": from_table,
            "fromColumn": from_column,
            "fromCardinality": from_cardinality,
            "toTable": to_table,
            "toColumn": to_column,
            "toCardinality": to_cardinality,
            "isActive": True,
            "crossFilteringBehavior": req.crossFilteringBehavior
        }
        remaining_defs, skipped_defs = await split_existing_relationship_definitions(session, [relationship_definition])
        if not remaining_defs:
            return {
                "status": "success",
                "data": {
                    "success": True,
                    "message": "This relationship already exists; nothing was changed."
                }
            }

        result = await asyncio.wait_for(session.call_tool("relationship_operations", {
            "request": {
                "operation": "Create",
                "definitions": remaining_defs,
                "options": {"useTransaction": True}
            }
        }), timeout=120.0)
        result_text = result.content[0].text if result.content else ""
        data = json.loads(result_text) if result_text else {}
        
        # Auto-clean if failed due to duplicates
        if data.get("success") is False or data.get("status") == "error" or data.get("errorMessage"):
            err_msg = (data.get("message") or data.get("errorMessage") or result_text).lower()
            if "duplicate" in err_msg or "doppelten" in err_msg:
                cleaned_any = False
                if to_cardinality == "One":
                    cleaned_any = await auto_clean_table(session, to_table, to_column) or cleaned_any
                if from_cardinality == "One":
                    cleaned_any = await auto_clean_table(session, from_table, from_column) or cleaned_any
                
                if cleaned_any:
                    # Retry
                    result = await asyncio.wait_for(session.call_tool("relationship_operations", {
                        "request": {
                            "operation": "Create",
                            "definitions": [{
                                "fromTable": from_table,
                                "fromColumn": from_column,
                                "fromCardinality": from_cardinality,
                                "toTable": to_table,
                                "toColumn": to_column,
                                "toCardinality": to_cardinality,
                                "isActive": True,
                                "crossFilteringBehavior": req.crossFilteringBehavior
                            }],
                            "options": {"useTransaction": True}
                        }
                    }), timeout=120.0)
                    result_text = result.content[0].text if result.content else ""
                    data = json.loads(result_text) if result_text else {}

        if data.get("success") is False or data.get("status") == "error" or data.get("errorMessage"):
            return {"status": "error", "message": data.get("message") or data.get("errorMessage") or result_text}
        return {"status": "success", "data": data}
    except json.JSONDecodeError:
        return {"status": "error", "message": "The MCP returned an unreadable relationship result"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/tool")
async def execute_tool(req: Request):
    data = await req.json()
    tool_name = data.get("tool_name")
    args = data.get("args")
    if not isinstance(tool_name, str) or not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="tool_name and args are required")

    allowed_tools = {
        "connection_operations", "model_operations", "table_operations",
        "column_operations", "measure_operations", "relationship_operations",
        "security_role_operations", "dax_query_operations"
    }
    if tool_name not in allowed_tools:
        raise HTTPException(status_code=403, detail="Tool is not available through this endpoint")

    request_data = args.get("request", {})
    operation = request_data.get("operation", "") if isinstance(request_data, dict) else ""
    if str(operation).lower() in {"create", "update", "delete", "remove", "drop", "rename", "alter", "refresh", "execute", "evaluate"}:
        raise HTTPException(status_code=403, detail="Use the chat workflow for write or query operations")
    try:
        session = await asyncio.wait_for(mcp_manager.connect(), timeout=15.0)
        result = await session.call_tool(tool_name, args)
        result_text = result.content[0].text if result.content else None
        return {"success": True, "result": result_text}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/tools")
async def get_tools():
    try:
        session = await asyncio.wait_for(mcp_manager.connect(), timeout=15.0)
        tools = await session.list_tools()
        # tools.tools is a list of Tool objects
        return {"tools": [{"name": t.name, "schema": t.inputSchema} for t in tools.tools]}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # Single-engine architecture: manager + dax/semantic/rls profiles.
    # The intelligence_mode flag is accepted for backward compatibility,
    # but all traffic goes through the multi-agent workflow.
    from api.multi_agent import chat_endpoint_multi_agent
    return await chat_endpoint_multi_agent(req)


@app.post("/api/proposals/{proposal_id}/accept")
async def accept_proposal(proposal_id: str):
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    proposal = proposals[proposal_id]
    if proposal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Proposal already processed")
        
    try:
        session = await mcp_manager.connect()
        
        # Check if relationship exists before creating
        operation = proposal.get("args", {}).get("request", {}).get("operation")
        if proposal["tool_name"] == "measure_operations" and str(operation).lower() in ["create", "createorreplace"]:
            measure_defs = proposal.get("args", {}).get("request", {}).get("definitions", []) or proposal.get("args", {}).get("definitions", [])
            err_msg, _ = await validate_measure_creation(session, measure_defs)
            if err_msg:
                return {
                    "status": "error",
                    "message": err_msg
                }

        if proposal["tool_name"] == "relationship_operations" and operation in ["Create", "CreateOrReplace"]:
            defs = proposal["args"]["request"].get("definitions", [])
            if defs:
                try:
                    validation_errors = await validate_relationship_definitions(session, defs)
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    return {
                        "status": "error",
                        "message": f"Could not validate the relationship proposal against the live model: {exc}"
                    }

                if validation_errors:
                    return {
                        "status": "error",
                        "message": (
                            "Relationship proposal rejected before execution because it contains "
                            "invalid schema references: " + " | ".join(validation_errors)
                        )
                    }

                try:
                    new_defs, skipped_defs = await split_existing_relationship_definitions(session, defs)
                    if not new_defs:
                        proposal["status"] = "accepted"
                        return {
                            "status": "success",
                            "result": json.dumps({
                                "success": True,
                                "message": f"All {len(skipped_defs)} requested relationships already exist; nothing was changed."
                            })
                        }
                        
                    proposal["args"]["request"]["definitions"] = new_defs
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    return {
                        "status": "error",
                        "message": f"Could not check existing relationships before creation: {exc}"
                    }

        if proposal["tool_name"] == "table_operations" and str(proposal.get("args", {}).get("request", {}).get("operation", "")).lower() == "create":
            proposal["args"] = normalize_table_create_request(proposal["args"])

        if proposal["tool_name"] == "relationship_operations" and proposal.get("args", {}).get("request", {}).get("operation") == "Delete":
            delete_defs = proposal["args"].get("request", {}).get("definitions", [])
            if delete_defs:
                try:
                    existing_res = await session.call_tool("relationship_operations", {
                        "request": {"operation": "List"}
                    })
                    existing_text = "".join(c.text for c in existing_res.content if hasattr(c, "text"))
                    existing_data = json.loads(existing_text) if existing_text else {}
                    existing_relationships = existing_data.get("data", existing_data.get("results", []))
                    if not isinstance(existing_relationships, list):
                        existing_relationships = []

                    live_refs = []
                    for definition in delete_defs:
                        exact = next((item for item in existing_relationships if relationship_matches(item, definition)), None)
                        if exact is None:
                            exact = next((item for item in existing_relationships if relationship_matches_reversed(item, definition)), None)
                        if exact is not None:
                            live = exact.get("data", exact) if isinstance(exact, dict) else {}
                            rel_name = live.get("name") if isinstance(live, dict) else None
                            # Fall back to the requested name when the live object has none.
                            if not rel_name and isinstance(definition, dict):
                                rel_name = definition.get("name")
                            if rel_name:
                                live_refs.append({"name": rel_name})

                    if not live_refs:
                        proposal["status"] = "accepted"
                        return {
                            "status": "success",
                            "result": json.dumps({
                                "success": True,
                                "message": "The requested relationship was already absent; nothing was deleted."
                            })
                        }

                    # Schema Delete uses references:[{name}], NOT definitions.
                    proposal["args"]["request"].pop("definitions", None)
                    proposal["args"]["request"]["references"] = live_refs
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    return {
                        "status": "error",
                        "message": f"Could not resolve the relationship before deletion: {exc}"
                    }
            
        # NOTE: relationship writes use plain Create — CreateOrReplace does not
        # exist for relationship_operations and the server rejects it.
            
        # Ensure the operation is committed to the model
        if "request" in proposal.get("args", {}):
            if "options" not in proposal["args"]["request"]:
                proposal["args"]["request"]["options"] = {}
            proposal["args"]["request"]["options"]["useTransaction"] = True
            
        result = await session.call_tool(proposal["tool_name"], proposal["args"])
        result_text = "".join([c.text for c in result.content if hasattr(c, "text")])
        print(f"[ACCEPT] tool={proposal['tool_name']} args={json.dumps(proposal['args'])} result={result_text}", flush=True)
        
        # Also log raw content for debugging
        for c in result.content:
            if hasattr(c, "type"):
                print(f"[ACCEPT] content type: {c.type}")
            if hasattr(c, "resource"):
                print(f"[ACCEPT] resource: {c.resource}")
        
        try:
            result_data = json.loads(result_text) if result_text else {}
        except json.JSONDecodeError:
            result_data = {}


        result_failed = (
            result_data.get("success") is False or
            result_data.get("status") == "error" or
            bool(result_data.get("errorMessage")) or
            any(
                isinstance(item, dict) and (
                    item.get("success") is False or
                    item.get("status") == "error" or
                    item.get("error") or
                    item.get("errorMessage")
                )
                for item in result_data.get("results", [])
            ) if isinstance(result_data.get("results"), list) else False
        )
        
        # Also check warnings for duplicates (Transaction rolled back)
        if not result_failed and "warnings" in result_data and any("doppelten" in w.lower() or "duplicate" in w.lower() for w in result_data["warnings"]):
            result_failed = True

        if result_failed and proposal["tool_name"] == "relationship_operations" and operation in ["Create", "CreateOrReplace"]:
            err_msg = result_text.lower()
            if "duplicate" in err_msg or "doppelten" in err_msg:
                defs = proposal["args"].get("request", {}).get("definitions", [])
                cleaned_any = False
                for d in defs:
                    if d.get("toCardinality") in ["One", "1"] or "lookup" in d.get("toTable", "").lower():
                        cleaned_any = await auto_clean_table(session, d.get("toTable"), d.get("toColumn")) or cleaned_any
                    if d.get("fromCardinality") in ["One", "1"] or "lookup" in d.get("fromTable", "").lower():
                        cleaned_any = await auto_clean_table(session, d.get("fromTable"), d.get("fromColumn")) or cleaned_any
                
                if cleaned_any:
                    result = await session.call_tool(proposal["tool_name"], proposal["args"])
                    result_text = "".join([c.text for c in result.content if hasattr(c, "text")])
                    try:
                        result_data = json.loads(result_text) if result_text else {}
                    except json.JSONDecodeError:
                        result_data = {}
                    
                    result_failed = (
                        result_data.get("success") is False or
                        result_data.get("status") == "error" or
                        bool(result_data.get("errorMessage")) or
                        any(
                            isinstance(item, dict) and (
                                item.get("success") is False or
                                item.get("status") == "error" or
                                item.get("error") or
                                item.get("errorMessage")
                            )
                            for item in result_data.get("results", [])
                        ) if isinstance(result_data.get("results"), list) else False
                    )

        if result_failed:
            return {"status": "error", "message": result_text or "MCP write failed"}
        proposal["status"] = "accepted"
        return {"status": "success", "result": result_text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str):
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    proposal = proposals[proposal_id]
    if proposal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Proposal already processed")
        
    proposal["status"] = "rejected"
    return {"status": "success", "message": "Proposal rejected. No model change was made."}

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Serve static frontend in production
dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # Allow API routes to pass through (this catch-all is at the bottom so API routes match first)
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        file_path = os.path.join(dist_path, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

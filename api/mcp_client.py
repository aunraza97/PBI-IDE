import os
import asyncio
import json
import csv
import io

PBI_MCP_COMMAND = os.getenv("PBI_MCP_COMMAND", "server/powerbi-modeling-mcp.exe")

class MockTool:
    def __init__(self, d):
        self.name = d.get("name")
        self.description = d.get("description")
        self.inputSchema = d.get("inputSchema")

class MockToolsResponse:
    def __init__(self, tools):
        self.tools = [MockTool(t) for t in tools]

class MockCallResultContent:
    def __init__(self, text):
        self.text = text

class MockCallResult:
    def __init__(self, text):
        self.content = [MockCallResultContent(text)]


def _content_value(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _parse_csv_rows(text):
    """Return structured rows when an MCP resource contains a CSV result set."""
    try:
        rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    except (csv.Error, TypeError):
        return []

    return [row for row in rows if any(value not in (None, "") for value in row.values())]


def normalize_tool_content(content):
    """Preserve text and embedded MCP resources in one JSON response.

    DAX execution metrics can include the query result as an embedded CSV resource.
    The previous client discarded all non-text blocks, leaving the LLM with only a
    successful execution acknowledgement and no value to report.
    """
    text_parts = []
    resources = []
    rows = []

    for block in content:
        block_type = _content_value(block, "type")
        if hasattr(block_type, "value"):
            block_type = block_type.value
        if block_type == "text":
            value = _content_value(block, "text", "")
            if value:
                text_parts.append(value)
            continue

        if block_type != "resource":
            continue

        resource = _content_value(block, "resource", {})
        if not isinstance(resource, dict):
            if hasattr(resource, "model_dump"):
                resource = resource.model_dump()
            elif hasattr(resource, "dict"):
                resource = resource.dict()
            else:
                resource = vars(resource)

        resource_text = resource.get("text")
        if not isinstance(resource_text, str):
            continue

        resource_info = {
            "uri": resource.get("uri"),
            "mimeType": resource.get("mimeType"),
            "text": resource_text,
        }
        resources.append(resource_info)
        if resource_info["mimeType"] in (None, "text/csv", "application/csv"):
            rows.extend(_parse_csv_rows(resource_text))

    text = "".join(text_parts)
    if not resources:
        return text

    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError:
        payload = {"message": text}

    if not isinstance(payload, dict):
        payload = {"message": text}
    payload["resources"] = resources

    if rows:
        data = payload.setdefault("data", {})
        if not isinstance(data, dict):
            data = payload["data"] = {}
        data["rows"] = rows
        data["rowCount"] = len(rows)

    return json.dumps(payload, ensure_ascii=False)

def resolve_refs(schema, root_schema=None):
    if root_schema is None:
        root_schema = schema
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/"):
                parts = ref_path[2:].split("/")
                current = root_schema
                try:
                    for part in parts:
                        current = current[part]
                    return resolve_refs(current, root_schema)
                except KeyError:
                    return {"type": "object"}
            return {"type": "object"}
        else:
            return {k: resolve_refs(v, root_schema) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [resolve_refs(item, root_schema) for item in schema]
    else:
        return schema

def convert_mcp_tools_to_openai(tools):
    openai_tools = []
    for tool in tools:
        resolved_schema = resolve_refs(tool.inputSchema) if tool.inputSchema else {
            "type": "object",
            "properties": {}
        }
        
        def inject_partitions(schema_obj):
            if isinstance(schema_obj, dict):
                if schema_obj.get("type") == "object" and "properties" in schema_obj:
                    props = schema_obj["properties"]
                    if "name" in props and "dataCategory" in props:
                        if "mExpression" not in props:
                            props["mExpression"] = {
                                "type": "string",
                                "description": "Power Query M-Code expression for this table."
                            }
                for k, v in schema_obj.items():
                    inject_partitions(v)
            elif isinstance(schema_obj, list):
                for item in schema_obj:
                    inject_partitions(item)

        if tool.name == "table_operations":
            inject_partitions(resolved_schema)

        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or f"Tool: {tool.name}",
                "parameters": resolved_schema
            }
        })
    return openai_tools

# Verified usage knowledge for every MCP tool, derived from live schema
# introspection. Appended to tool descriptions so the LLM always sees the
# exact operations, shapes, and casing — never guess them.
# Universal rules: every call is {"request": {"operation": "<Op>", ...}}.
# Operation names are PascalCase and case-sensitive. connectionName is
# optional everywhere (omit it — the server uses the last connection).
# NEVER invent operations: no CreateOrReplace (except nothing uses it),
# no Evaluate (dax uses Execute), no GetDatabaseInfo (does not exist).
TOOL_USAGE_GUIDES = {
    "table_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Refresh, Rename, "
        "MarkAsDateTable, GetSchema, ExportTMDL, ExportTMSL. "
        "List takes NOTHING (no filter, no references). Get/Delete/Refresh/GetSchema/Export "
        "take references:[{name}] (name only). Create/Update take definitions[] with "
        "name + mExpression + columns[{name, dataType, sourceColumn}]. "
        "Rename takes renameDefinitions:[{currentName, newName}]. "
        "dataType must be TOM casing: String, Int64, Double, DateTime, Decimal, Boolean "
        "(never text/integer/datetime lowercase)."
    ),
    "column_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, ExportTMDL. "
        "List takes filter:{tableNames?, displayFolders?, maxResults?} — NEVER references. "
        "Get/Delete/ExportTMDL take references:[{tableName, name}] (BOTH required). "
        "Create/Update take definitions[] with tableName + name + sourceColumn/expression + dataType. "
        "Rename takes renameDefinitions:[{tableName, currentName, newName}]."
    ),
    "partition_operations": (
        "VERIFIED OPS: Help, List, Get, Create, Update, Delete, Refresh, Rename, ExportTMDL, ExportTMSL. "
        "List takes filter:{tableName?, maxResults?}. Get/Delete take "
        "references:[{tableName, name?}] (name optional only for single-partition tables). "
        "Create/Update take definitions:[{tableName, name, expression, sourceType?, mode?}] — there is "
        "NO 'partition' key, use definitions. Refresh takes "
        "refreshDefinitions:[{tableName, name?, refreshType?}] (refreshType: Automatic|Full|ClearValues|"
        "Calculate|DataOnly|Defragment). Rename takes renameDefinitions:[{tableName, newName, currentName?}]."
    ),
    "model_operations": (
        "VERIFIED OPS: Help, Get, Create, Update, Refresh, GetStats, Rename, ExportTMDL. "
        "No List/Delete/ExportTMSL. Create/Update take singular definition:{...} (NOT definitions). "
        "Get/GetStats take only optional modelName. Refresh takes only refreshType "
        "(Automatic|Full|ClearValues|Calculate|DataOnly|Defragment) — whole-model only, no per-table "
        "objects, no 'type' key. Rename needs newName."
    ),
    "database_operations": (
        "VERIFIED OPS: Help, List, Update, ImportFromTmdlFolder, ExportToTmdlFolder, DeployToFabric, "
        "Create, ExportTMDL, ExportTMSL. No Get/Delete/Refresh/Rename — there is NO GetDatabaseInfo op. "
        "List takes nothing. Create takes createDefinition:{...}. "
        "ImportFromTmdlFolder/ExportToTmdlFolder require tmdlFolderPath (server-local absolute path)."
    ),
    "measure_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, Move, ExportTMDL. "
        "No CreateOrReplace. Create takes definitions:[{name, tableName, expression, formatString?}] — "
        "tableName is REQUIRED on Create (Update cannot move tables; use Move with "
        "moveDefinitions:[{name, destinationTableName}]). Get/Delete take references:[{name, tableName?}] "
        "(tableName optional only if the name is unique). List takes filter:{tableNames?} — never "
        "references. Rename takes renameDefinitions:[{currentName, newName, tableName?}]."
    ),
    "dax_query_operations": (
        "VERIFIED OPS: Help, Execute, Validate. NEVER Evaluate (does not exist). "
        "Execute takes {query, timeoutSeconds?, maxRows?, getExecutionMetrics?}. "
        "query must be a full DAX query starting with EVALUATE (wrap scalars as "
        'EVALUATE ROW("Result", <expr>)). Validate syntax-checks only.'
    ),
    "calculation_group_operations": (
        "VERIFIED OPS (prefixes mandatory, no bare Create/List/Get): CreateGroup, UpdateGroup, "
        "DeleteGroup, GetGroup, ListGroups, RenameGroup, CreateItems, UpdateItems, DeleteItems, "
        "GetItems, ListItems, RenameItems, ReorderItems, ExportTMDL. "
        "Groups: groupDefinitions[] / groupReferences:[{name}] / renameGroupDefinitions. "
        "Items: itemDefinitions[] ({calculationGroupName, name, expression, ordinal, ...}) / "
        "itemReferences:[{calculationGroupName, name}] / renameItemsDefinitions. "
        "ListItems REQUIRES itemFilter:{calculationGroupName}. ListGroups takes nothing."
    ),
    "function_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, ExportTMDL. "
        "Model-scoped (NO tableName). Create/Update take definitions:[{name, expression, description?}]. "
        "Get/Delete take references:[{name}] (name only). List takes nothing."
    ),
    "relationship_operations": (
        "VERIFIED OPS: Help, List, Get, Create, Update, Delete, Rename, Activate, Deactivate, Find, "
        "ExportTMDL. NEVER CreateOrReplace (does not exist). List takes nothing (no filter). "
        "Get/Delete/Activate/Deactivate/ExportTMDL take references:[{name}] (name ONLY, no tableName). "
        "Create/Update take definitions:[{fromTable, fromColumn, fromCardinality?, toTable, toColumn, "
        "toCardinality?, isActive?, crossFilteringBehavior?}]. Rename takes "
        "renameDefinitions:[{currentName, newName}]."
    ),
    "security_role_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, CreatePermissions, "
        "UpdatePermissions, DeletePermissions, GetPermissions, ListPermissions, GetEffectivePermissions, "
        "ExportTMDL, ExportTMSL. List takes nothing. Get/Delete take references:[{name}]. "
        "To read a role's DAX filter use Get (NOT GetPermissions without tableName). To CHANGE a DAX "
        "filter use UpdatePermissions with permissionDefinitions:[{roleName, tableName, "
        "filterExpression?}] — NEVER plain Update. GetPermissions/DeletePermissions take "
        "permissionReferences:[{roleName, tableName}] (BOTH required). ListPermissions takes "
        "permissionFilter:{roleName}. ModelPermission values are Title Case: Read, Administrator, None."
    ),
    "perspective_operations": (
        "VERIFIED OPS include List, Get, Create, Update, Delete, Rename, ExportTMDL plus scoped "
        "ListTables/GetTables/AddTables/UpdateTables/RemoveTables, ListColumns/GetColumns/AddColumns/"
        "RemoveColumns, ListMeasures/GetMeasures/AddMeasures/RemoveMeasures, ListHierarchies/GetHierarchies/"
        "AddHierarchies/RemoveHierarchies. List takes nothing. Scoped List* take "
        "filter:{perspectiveName (required), tableName?, maxResults?}. Mutators take TOP-LEVEL "
        "perspectiveName (not inside filter) plus tables[]/columns[]/measures[]/hierarchies[] "
        "(e.g. AddTables takes tables:[{tableName, includeAll?}]). NEVER put definitions[] on Add* ops."
    ),
    "culture_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, GetValidNames, GetValidDetails, "
        "GetDetailsByName, GetDetailsByLCID, ExportTMDL. The key is always name in BCP-47 format "
        "(e.g. fr-FR) — never cultureName. Create/Update take definitions:[{name, ...}]. "
        "Get/Delete take references:[{name}]. Rename takes renameDefinitions:[{currentName, newName}]. "
        "List takes nothing. GetDetailsByLCID takes lcid (integer, e.g. 1036)."
    ),
    "object_translation_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List (no Rename/Export). "
        "Every definition/reference REQUIRES the triple cultureName + property + objectType "
        "(objectType: Model|Table|Measure|Column|Hierarchy|Level|KPI). Point at objects with "
        "tableName/measureName/columnName/hierarchyName/levelName (NOT name). "
        "List takes filter:{cultureName?, objectType?, objectName?, maxResults?}. "
        "On Create, set createCultureIfNotExists:true if the culture may not exist."
    ),
    "user_hierarchy_operations": (
        "VERIFIED OPS: Help, List, Get, Create, Update, Delete, Rename, GetColumns, AddLevels, "
        "RemoveLevels, UpdateLevels, RenameLevels, ReorderLevels, ExportTMDL. "
        "Hierarchy identity is tableName + hierarchyName (NEVER bare name): Get/Delete take "
        "references:[{tableName, hierarchyName}]. Create/Update take definitions:[{tableName, name, "
        "levels:[{name, columnName, ordinal?}]}]. Level ops use their own buckets: levelDefinitions[] "
        "and levelReferences:[{tableName, hierarchyName, levelName}] (NOT definitions/references). "
        "RenameLevels takes renameLevelsDefinitions with currentLevelName/newLevelName. ReorderLevels "
        "takes reorderLevelsDefinitions with levelNamesInOrder[]. shouldCascadeDelete defaults FALSE here."
    ),
    "calendar_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, ExportTMDL, CreateColumnGroups, "
        "UpdateColumnGroups, DeleteColumnGroups, GetColumnGroups, ListColumnGroups. "
        "Create REQUIRES name + tableName. Get/Delete take references:[{name, tableName}]. "
        "List takes filter:{tableName?, maxResults?}. ListColumnGroups takes "
        "columnGroupFilter:{calendarName (required), tableName?}. Requires compatibility level >= 1701."
    ),
    "named_expression_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, Rename, CreateParameter, UpdateParameter, "
        "ExportTMDL. Create/Update/CreateParameter/UpdateParameter take definitions:[{name (required), "
        "expression?, kind?, queryGroupName?, ...}] where kind is exactly M (Power Query) or DAX. "
        "The expression field is MANDATORY on writes — never send a definition without one. "
        "Get/Delete take references:[{name}]. List takes nothing (no filter). "
        "Rename takes renameDefinitions:[{currentName, newName}]. "
        "NEVER use this tool for data tables (Table.Combine/Csv.Document belong in table_operations "
        "Create, not here) — named expressions cannot hold tables."
    ),
    "query_group_operations": (
        "VERIFIED OPS: Help, Create, Update, Delete, Get, List, ExportTMDL (NO Rename — use Delete+Create). "
        "Create takes definitions without name (use description/folder); Update takes "
        "definitions:[{name, folder?, ...}]. Get/Delete take references:[{name}]. List takes nothing."
    ),
    "trace_operations": (
        "VERIFIED OPS: Help, Start, Stop, Pause, Resume, Clear, Get, List, ExportJSON (if Fetch is "
        "rejected try Report — description and schema disagree on the name). Start takes events[] "
        "(e.g. QueryBegin, QueryEnd, Error) + filterCurrentSessionOnly (default true). ExportJSON "
        "requires filePath (server-local). Fetch takes columns[] + clearAfterFetch?."
    ),
    "transaction_operations": (
        "VERIFIED OPS: Help, Begin, Commit, Rollback, GetStatus, ListActive. Only 3 keys exist: "
        "operation, connectionName, transactionId — NO definitions/references. Begin REQUIRES "
        "connectionName. Commit/Rollback/GetStatus REQUIRE transactionId. ListActive takes nothing."
    ),
    "connection_operations": (
        "VERIFIED OPS include Help, Connect, ConnectFabric, Disconnect, GetConnection, ListConnections, "
        "ListLocalInstances, RenameConnection, ClearLastUsed, GetLastUsed, SetLastUsed, ConnectFolder. "
        "Connect takes connectionString (Data Source=...) — NEVER send connectionName on Connect or "
        "ConnectFabric (it is auto-generated). ConnectFabric takes exact workspaceName + "
        "semanticModelName. Disconnect/RenameConnection/SetLastUsed REQUIRE connectionName. "
        "RenameConnection takes oldConnectionName + newConnectionName."
    ),
}


def annotate_tool_guides(openai_tools):
    """Append verified usage knowledge to each tool description in place."""
    for t in openai_tools:
        try:
            fn = t.get("function", {})
            guide = TOOL_USAGE_GUIDES.get(fn.get("name", ""), "")
            if guide and guide not in (fn.get("description") or ""):
                fn["description"] = (fn.get("description") or "") + "\n\nUSAGE (verified): " + guide
        except Exception:
            pass
    return openai_tools

class MCPConnectionManager:
    def __init__(self):
        self.proc = None
        self.req_id = 1
        self.lock = asyncio.Lock()
        self.stderr_task = None

    async def _drain_stderr(self):
        while self.proc and self.proc.stderr:
            line = await self.proc.stderr.readline()
            if not line:
                break

    async def _reset_process(self):
        proc = self.proc
        self.proc = None
        if self.stderr_task:
            self.stderr_task.cancel()
            self.stderr_task = None
        if proc and proc.returncode is None:
            proc.terminate()

    async def connect(self):
        if self.proc is not None and self.proc.returncode is not None:
            await self._reset_process()

        if self.proc is None:
            cmd_path = PBI_MCP_COMMAND
            if not os.path.isabs(cmd_path):
                cmd_path = os.path.join(os.getcwd(), cmd_path)
            
            self.proc = await asyncio.create_subprocess_exec(
                cmd_path, "--start",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024 * 10
            )
            self.stderr_task = asyncio.create_task(self._drain_stderr())
            
            req = {
                "jsonrpc": "2.0",
                "id": self.req_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pbi-ide", "version": "1.0"}
                }
            }
            self.req_id += 1
            self.proc.stdin.write(json.dumps(req).encode('utf-8') + b'\n')
            await self.proc.stdin.drain()
            
            try:
                line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=15.0)
                response = json.loads(line.decode("utf-8"))
                if response.get("id") != req["id"] or "error" in response:
                    raise Exception(response.get("error", {}).get("message", "MCP initialization failed"))
            except Exception:
                await self._reset_process()
                raise
            
            notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            self.proc.stdin.write(json.dumps(notif).encode('utf-8') + b'\n')
            await self.proc.stdin.drain()
            
        return self

    async def list_tools(self):
        async with self.lock:
            req = {
                "jsonrpc": "2.0",
                "id": self.req_id,
                "method": "tools/list"
            }
            self.req_id += 1
            self.proc.stdin.write(json.dumps(req).encode('utf-8') + b'\n')
            await self.proc.stdin.drain()
            
            try:
                while True:
                    line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=30.0)
                    if not line:
                        raise Exception("MCP server process closed connection")
                    resp = json.loads(line.decode('utf-8'))
                    if resp.get("id") == req["id"]:
                        break
                if "error" in resp:
                    raise Exception(resp["error"].get("message", "MCP tools/list failed"))
                tools = resp.get("result", {}).get("tools", [])
            except Exception:
                await self._reset_process()
                raise
            return MockToolsResponse(tools)

    async def call_tool(self, name, args):
        async with self.lock:
            req = {
                "jsonrpc": "2.0",
                "id": self.req_id,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": args
                }
            }
            self.req_id += 1
            self.proc.stdin.write(json.dumps(req).encode('utf-8') + b'\n')
            await self.proc.stdin.drain()
            
            try:
                while True:
                    line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=600.0)
                    if not line:
                        raise Exception("MCP server process closed connection unexpectedly")

                    try:
                        resp = json.loads(line.decode('utf-8'))
                    except json.JSONDecodeError:
                        continue

                    if resp.get("id") != req["id"]:
                        continue
                    if "error" in resp:
                        raise Exception(resp["error"].get("message", "Unknown error"))
                    break
            except Exception:
                await self._reset_process()
                raise
                
            content = resp.get("result", {}).get("content", [])
            return MockCallResult(normalize_tool_content(content))
            
    async def close(self):
        await self._reset_process()

mcp_manager = MCPConnectionManager()

import json



import uuid



import asyncio



import re
import traceback



from fastapi.responses import StreamingResponse



from api.llm_router import call_llm



from api.mcp_client import mcp_manager, convert_mcp_tools_to_openai, annotate_tool_guides



from api.main import (



    config_mgr,



    conversation_histories,



    proposals,



    validate_measure_creation,



    normalize_table_create_request,




    maybe_inject_confirmation,

)







async def validate_table_operations_create(target_agent, t_args, operation, current_messages, tc):



    """



    Validate and normalize table_operations Create request.



    Returns (table_err, t_args) tuple.



    """



    table_err = None



    



    defs = t_args.get("request", {}).get("definitions", []) if "request" in t_args else t_args.get("definitions", [])







    name_only_idx = None



    expr_only_idx = None



    for i, t_def in enumerate(defs):



        if not isinstance(t_def, dict):



            continue



        if "daxExpression" in t_def and t_def["daxExpression"]:



            table_err = "ERROR: You provided 'daxExpression' for a table. You MUST use 'mExpression' (Power Query M-Code) instead. Retry with mExpression containing Table.Combine()."



            break



        if operation.lower() == "create" and "name" in t_def and "partitionName" not in t_def and "roleName" not in t_def:



            if "mExpression" not in t_def and "partitions" not in t_def and "source" not in t_def:



                name_only_idx = i



        if "name" not in t_def and ("mExpression" in t_def or "source" in t_def):



            expr_only_idx = i







    if table_err is None and name_only_idx is not None:



        if expr_only_idx is not None:



            # The LLM split name and mExpression into two array entries ï¿½ merge them.



            # defs is a live reference into t_args, so in-place edits are enough.



            merged_name = defs[name_only_idx].get("name", "")



            defs[name_only_idx]["mExpression"] = defs[expr_only_idx].get("mExpression") or defs[expr_only_idx].get("source")



            del defs[expr_only_idx]



            tc["function"]["arguments"] = json.dumps(t_args)



            print(f"[{target_agent}] Auto-merged split definition for '{defs[name_only_idx].get('name', '')}' into a single object.")



        else:



            table_err = "ERROR: Missing 'mExpression' in the table definition that has 'name'. The definitions array must contain ONE object per table that has BOTH fields together, e.g. { \"name\": \"Sales Data\", \"mExpression\": \"let ... in ...\" }."








    # After merge, ensure each Create definition with mExpression has columns.



    # If columns are missing, try to extract them from source tables referenced in M-Code



    # by scanning prior tool responses in current_messages.



    if table_err is None:



        for t_def in defs:



            if not isinstance(t_def, dict):



                continue



            if operation.lower() == "create" and "mExpression" in t_def and t_def.get("mExpression") and ("columns" not in t_def or not t_def.get("columns")):



                # Try to extract source table names from M-Code



                mexpr = t_def.get("mExpression", "")



                # Look for Table.Combine({Table1, Table2, ...}) or similar patterns



                combine_match = re.search(r"Table\.Combine\s*\(\s*\{([^}]+)\}\s*\)", mexpr)



                if combine_match:



                    table_refs_str = combine_match.group(1)
                    # Split refs, keeping only real table identifiers. Inline expressions such as
                    # Csv.Document(File.Contents("C:\\..."), ...) contain commas that must NOT
                    # be mistaken for table names.
                    source_table_names = []
                    for _m in re.finditer(r'#"([^"]+)"', table_refs_str):
                        _cand = _m.group(1)
                        if _cand and not any(_ch in _cand for _ch in ("\\", "/", ":")):
                            source_table_names.append(_cand)
                    bare_scan = re.sub(r'"[^"]*"', "", table_refs_str)
                    bare_scan = re.sub(r"'[^']*'", '', bare_scan)
                    for _tok in re.split(r'[,\s]+', bare_scan):
                        _t = _tok.strip().strip("'")
                        if _t and re.fullmatch(r'[A-Za-z_]\w*', _t):
                            source_table_names.append(_t)
                    print(f"[{target_agent}] Detected source tables in mExpression: {source_table_names}")







                    # Search conversation history for Get responses containing these tables



                    columns_by_table = {}



                    for msg in current_messages:



                        if msg.get("role") == "tool" and msg.get("name") == "table_operations":



                            try:



                                content = msg.get("content", "")



                                if isinstance(content, str) and content.strip():



                                    tool_result = json.loads(content)



                                    # Handle both wrapped and direct results



                                    results = tool_result.get("results", tool_result.get("data", []))



                                    if isinstance(results, list):



                                        for res in results:



                                            data = res.get("data", res) if isinstance(res, dict) else res



                                            if isinstance(data, dict):



                                                tbl_name = data.get("name", "")



                                                # Fuzzy match: M-Code uses step names (no spaces), model uses display names (with spaces)



                                                # e.g. "SalesData2020" vs "Sales Data 2020"



                                                matched = False



                                                for src_name in source_table_names:



                                                    # Normalize both: remove spaces, lower case



                                                    norm_src = src_name.replace(" ", "").lower()



                                                    norm_tbl = tbl_name.replace(" ", "").lower()



                                                    if norm_src == norm_tbl:



                                                        matched = True



                                                        break



                                                if matched:



                                                    # Extract columns



                                                    cols = data.get("columns", [])



                                                    if cols:



                                                        columns_by_table[tbl_name] = cols



                            except Exception:



                                pass







                    if columns_by_table:



                        # Use columns from the first source table (they should be identical)



                        first_cols = next(iter(columns_by_table.values()))



                        if first_cols:



                            t_def["columns"] = first_cols



                            tc["function"]["arguments"] = json.dumps(t_args)



                            print(f"[{target_agent}] Auto-injected {len(first_cols)} columns from matched source tables into '{t_def.get('name')}'")



                        else:



                            table_err = "ERROR: Source tables found but have no column definitions."



                    else:



                        # No fuzzy match - fall back to using columns from ANY table



                        # returned by the prior Get operation (the tables the user wants to combine)



                        fallback_cols = None



                        for msg in current_messages:



                            if msg.get("role") == "tool" and msg.get("name") == "table_operations":



                                try:



                                    content = msg.get("content", "")



                                    if isinstance(content, str) and content.strip():



                                        tool_result = json.loads(content)



                                        results = tool_result.get("results", tool_result.get("data", []))



                                        if isinstance(results, list):



                                            for res in results:



                                                data = res.get("data", res) if isinstance(res, dict) else res



                                                if isinstance(data, dict):



                                                    cols = data.get("columns", [])



                                                    if cols:



                                                        fallback_cols = cols



                                                        break



                                except Exception:



                                    pass



                            if fallback_cols:



                                break







                        if fallback_cols:



                            t_def["columns"] = fallback_cols



                            tc["function"]["arguments"] = json.dumps(t_args)



                            print(f"[{target_agent}] Auto-injected {len(fallback_cols)} columns from prior Get response (fallback) into '{t_def.get('name')}'")



                        else:



                            table_err = "ERROR: When creating a table using 'mExpression', you MUST explicitly provide the 'columns' array. No source table columns could be determined. Please include columns like [{\"name\": \"OrderDate\", \"dataType\": \"dateTime\"}, ...]."



                else:



                    table_err = "ERROR: When creating a table using 'mExpression', you MUST explicitly provide the 'columns' array (e.g. [{\"name\":\"ID\",\"dataType\":\"int64\"}, ...]). The schema cannot be inferred automatically by the engine."







                # NEW: Validate M-Code Table.Combine references against known table names



                # Check for missing #"..." quoting on names with spaces



                if table_err is None and combine_match:



                    try:



                        # Collect all known table names from prior Get responses



                        known_table_names = set()



                        for msg in current_messages:



                            if msg.get("role") == "tool" and msg.get("name") == "table_operations":



                                try:



                                    content = msg.get("content", "")



                                    if isinstance(content, str) and content.strip():



                                        tool_result = json.loads(content)



                                        results = tool_result.get("results", tool_result.get("data", []))



                                        if isinstance(results, list):



                                            for res in results:



                                                data = res.get("data", res) if isinstance(res, dict) else res



                                                if isinstance(data, dict):



                                                    tbl_name = data.get("name", "")



                                                    if tbl_name:



                                                        known_table_names.add(tbl_name)



                                except Exception:



                                    pass







                        # For each known table name with spaces, check if it's properly quoted in M-Code



                        for known_name in known_table_names:



                            if " " in known_name:



                                # Check if M-Code contains #"Known Name" (properly quoted)



                                bare_name = known_name.replace(" ", "")



                                bare_in_mexpr = bare_name in mexpr and f'#"{known_name}"' not in mexpr



                                



                                if bare_in_mexpr:



                                    table_err = (
                                                f"ERROR: M-Code references '{bare_name}' but the actual table name is '{known_name}' (with spaces). "
                                                f"In Power Query M, names with spaces MUST be wrapped in #\"...\" -- use #\"{known_name}\" instead. "
                                                f"Fix your Table.Combine to reference #\"{known_name}\"."
                                            )



                                    print(f"[{target_agent}] M-CODE VALIDATION FAILED: {table_err}")



                                    break



                    except Exception as val_err2:



                        print(f"[{target_agent}] M-Code reference validation FAILED: {val_err2}")



    



    if table_err is None and operation.lower() == "create":
        from api.generate_semantic_model import heal_redundant_promote_headers
        updated_any = False
        for t_def in defs:
            if isinstance(t_def, dict) and isinstance(t_def.get("mExpression"), str):
                healed = heal_redundant_promote_headers(t_def["mExpression"])
                if healed != t_def["mExpression"]:
                    t_def["mExpression"] = healed
                    updated_any = True
        if updated_any:
            tc["function"]["arguments"] = json.dumps(t_args)

    return table_err, t_args







async def chat_endpoint_multi_agent(req):



    session_id = req.session_id or str(uuid.uuid4())



    server_conversation_history = conversation_histories.setdefault(session_id, [])



    settings = config_mgr.load()







    new_user_msg = req.messages[-1]



    user_text = str(new_user_msg.get("content", ""))



    server_conversation_history.append({"role": "user", "content": user_text})

    # Resolve "yes"-style replies to the assistant's previous question
    # into an explicit instruction, so the agent acts instead of re-asking.
    confirmed_this_turn = maybe_inject_confirmation(server_conversation_history)
    async def event_generator():



        try:



            # 1. Connect to MCP to get tools



            session = await asyncio.wait_for(mcp_manager.connect(), timeout=15.0)



            tools_response = await asyncio.wait_for(session.list_tools(), timeout=15.0)



            all_tools = convert_mcp_tools_to_openai(tools_response.tools)

            # Attach verified per-tool usage knowledge ("training"): exact ops,
            # shapes, casing, and NEVER-rules derived from live schema analysis.
            all_tools = annotate_tool_guides(all_tools)

            print(f"[MCP] Exposed tools: {[t.get('function', {}).get('name') for t in all_tools]}")

            # Fail visibly (instead of narrating forever) when the MCP server
            # does not expose the relationship tool AND the user asked about
            # relationships. (NOTE: reads req.messages directly — user_text is
            # rebound later in this function, which would shadow it here.)
            _latest_user_text = str((req.messages[-1] or {}).get("content", "")).lower()
            if ("relationship_operations" not in {t.get("function", {}).get("name") for t in all_tools}
                    and "relationship" in _latest_user_text):
                yield f"data: {json.dumps({'type': 'message', 'content': 'Note: the connected Power BI service does not expose relationship tools, so I cannot list or analyze relationships right now. Table and measure analysis still work.'})}\n\n"; _msg_yielded_this_run = True



            



            # Inject internal tools



            all_tools.append({



                "type": "function",



                "function": {



                    "name": "generate_semantic_model",



                    "description": "Reads a local directory of CSV/Excel files, analyzes the headers, and proposes a semantic model. Use this ONLY when the user explicitly asks to generate, make, or build a full semantic model from local files. Do NOT use it for inspection questions (counting/listing files) or for combining files into a single table — for a single-table combine use table_operations Create instead.",



                    "parameters": {



                        "type": "object",



                        "properties": {



                            "folder_path": {



                                "type": "string",



                                "description": "The absolute local path to the folder containing the CSV files."



                            }



                        },



                        "required": ["folder_path"]



                    }



                }



            })

            all_tools.append({

                "type": "function",

                "function": {

                    "name": "list_folder_files",

                    "description": "Lists the files in a local folder (recursive, read-only). Use this when the user asks inspection questions such as how many files are in a folder, what Excel/CSV files exist, or what is inside a directory. Report the counts/names from the result and ASK before building or creating anything.",

                    "parameters": {

                        "type": "object",

                        "properties": {

                            "folder_path": {

                                "type": "string",

                                "description": "The absolute local path of the folder to list."

                            }

                        },

                        "required": ["folder_path"]

                    }

                }

            })

            all_tools.append({

                "type": "function",

                "function": {

                    "name": "read_file_headers",

                    "description": "Reads the column headers of specific CSV/Excel files on disk (read-only). Use this when you need the schema of loose files before proposing a table (e.g. to combine several files into one table with the correct mExpression and columns). Pass the full file paths.",

                    "parameters": {

                        "type": "object",

                        "properties": {

                            "file_paths": {

                                "type": "array",

                                "items": {"type": "string"},

                                "description": "Absolute paths of the CSV/Excel files to read."

                            }

                        },

                        "required": ["file_paths"]

                    }

                }

            })







            # 2. Manager Routing



            manager_prompt = (



                "You are the Manager Agent for a Power BI assistant. "



                "Your job is to read the conversation and decide if you should answer directly or route to a specialized agent.\n"



                "If the user is making general conversation (e.g., 'Hi', 'Thanks', 'How are you'), answer them directly.\n"



                "If the user wants to work on the Power BI model, route to one of these agents:\n"



                "- 'dax_agent' for measures, DAX expressions, KPIs, and calculations ONLY.\n"



                "- 'rls_agent' for row-level security, roles, and permissions.\n"



                "- 'semantic_agent' for EVERYTHING else: tables, columns, relationships, M-Code, Power Query, combining/merging tables, creating new tables, reading/analyzing the schema, generating models.\n"



                "- READ-ONLY QUESTIONS: If the user only asks to inspect, count, list, or describe files in a folder (e.g. 'how many sales files do you see in this folder?'), route to 'semantic_agent' but the agent must ONLY report what it finds and then ASK before building anything. Do NOT auto-generate a model or create tables.\n"



                "CRITICAL ROUTING RULES:\n"



                "- If the user mentions 'M Code', 'Power Query', 'combine tables', 'merge tables', 'append tables', or 'create a table', ALWAYS route to 'semantic_agent'.\n"



                "- 'semantic_agent' handles ALL table-level work. 'dax_agent' ONLY handles DAX measures.\n"



                "You MUST respond ONLY with a JSON object. Format exactly like this:\n"



                "If answering directly: {\"route\": \"none\", \"response\": \"Hello! I am your assistant...\"}\n"



                "If routing: {\"route\": \"semantic_agent\", \"thought\": \"Routing to Semantic agent for table changes...\"}"



            )



            



            manager_messages = [{"role": "system", "content": manager_prompt}]



            for m in server_conversation_history:



                if m["role"] != "system" and not m.get("content", "").startswith("[System Status]"):



                    clean_m = {k: v for k, v in m.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id"]}



                    if "content" not in clean_m:



                        clean_m["content"] = ""



                    manager_messages.append(clean_m)



            



            # --- Keyword-based routing override ---



            # Some requests are so obviously table-related that we skip the LLM manager entirely.



            user_text = server_conversation_history[-1].get("content", "").lower() if server_conversation_history else ""



            combine_keywords = ["combine table", "merge table", "append table", "combine them", "merge them", "append them",



                                "m code", "m-code", "power query", "into one table", "into a single table",



                                "union table", "consolidate table", "join table"]



            force_semantic = any(kw in user_text for kw in combine_keywords)



            



            if force_semantic:



                target_agent = "semantic_agent"



                thought = "Routing to Semantic agent for combining tables using M Code or Power Query..."



                print(f"[MANAGER] Keyword override -> semantic_agent (matched in: '{user_text[:80]}...')")



            else:



                yield f"data: {{ \"type\": \"thought_chunk\", \"content\": \"Manager is analyzing the request... \" }}\n\n"



            



                try:
                    router_stream = await asyncio.to_thread(call_llm, manager_messages, [], settings, stream=True)
                except Exception as router_err:
                    print(f"[MANAGER] Router LLM unavailable: {router_err}")
                    traceback.print_exc()
                    yield f"data: {json.dumps({'type': 'message', 'content': 'The AI model is temporarily unavailable (the provider returned an error), so I could not process that request. Nothing in your Power BI model was changed. Please try again shortly, or check your model/provider settings.'})}\n\n"; _msg_yielded_this_run = True
                    yield "data: [DONE]\n\n"
                    return



                manager_output = ""



                for chunk in router_stream:



                    if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta:



                        content = getattr(chunk.choices[0].delta, 'content', '')



                        if content:



                            manager_output += content



            



                # Parse JSON - LLMs sometimes output malformed JSON (e.g. extra quotes)



                manager_decision = None



                try:



                    start = manager_output.find("{")



                    end = manager_output.rfind("}")



                    if start != -1 and end != -1:



                        json_str = manager_output[start:end+1]



                        manager_decision = json.loads(json_str)



                except json.JSONDecodeError:



                    pass



                



                # Regex fallback for malformed JSON



                if manager_decision is None:






                    route_match = re.search(r'"route"\s*:\s*"([^"]*)"', manager_output)



                    response_match = re.search(r'"response"\s*:\s*"(.*)', manager_output, re.DOTALL)



                    thought_match = re.search(r'"thought"\s*:\s*"(.*?)"\s*[,}]', manager_output, re.DOTALL)



                    



                    route_val = route_match.group(1) if route_match else "none"



                    response_val = response_match.group(1) if response_match else manager_output.strip()
                    if response_match:
                        response_val = response_match.group(1)
                        response_val = response_val.rstrip()
                        if response_val.endswith('"'):
                            response_val = response_val[:-1]
                        if response_val.endswith('}'):
                            response_val = response_val[:-1]
                        if response_val.endswith(','):
                            response_val = response_val[:-1]
                        response_val = response_val.strip()



                    thought_val = thought_match.group(1) if thought_match else None



                    



                    manager_decision = {"route": route_val, "response": response_val}



                    if thought_val:



                        manager_decision["thought"] = thought_val



                    print(f"[MANAGER] Used regex fallback for malformed JSON")



            



                target_agent = manager_decision.get("route", "none")



                print(f"[MANAGER] LLM decision: route={target_agent}, raw={manager_output[:200]}")



            



                if target_agent == "none" or target_agent not in ["dax_agent", "rls_agent", "semantic_agent"]:



                    # Manager answers directly



                    response_text = manager_decision.get("response", "I'm not sure how to route that. How can I help you today?")



                    yield f"data: {json.dumps({'type': 'message', 'content': response_text})}\n\n"; _msg_yielded_this_run = True



                    server_conversation_history.append({"role": "assistant", "content": response_text})



                    yield "data: [DONE]\n\n"



                    return



            



                thought = manager_decision.get("thought", f"Routing to {target_agent}...")



            



            # --- Handing off to sub-agent ---



            yield f"data: {{ \"type\": \"agent_handoff\", \"from\": \"manager\", \"to\": \"{target_agent}\", \"status\": \"routing\" }}\n\n"



            yield f"data: {{ \"type\": \"thought_chunk\", \"content\": \"\\n{thought}\\n\" }}\n\n"



            



            # Define Sub-Agent Prompts



            base_rules = (



                "\nCRITICAL TOOL RULES & SYNONYM MAPPING:\n"



                "You have access to several specialized tools. Use the following cheat sheet to map the user's intent or synonyms to the correct tool and operation:\n"



                "1. Intent: 'Analyze', 'Summarize', 'Review', 'Read schema', 'Get model', 'what model is connected', 'connected models', 'report name' -> Tool: `connection_operations` (Operation: GetConnection or ListConnections) to read the actual instance/PBIX name, then `model_operations` (Operation: Get) for model identity, `table_operations` (Operation: List) for tables and `measure_operations` (Operation: List) for measures.\n"



                "2. Intent: 'Table', 'M-Code', 'Power Query', 'Entity', 'View' -> Tool: `table_operations`\n"



                "3. Intent: 'DAX', 'Measure', 'Calculation', 'KPI', 'Metric' -> Tool: `measure_operations`\n"



                "4. Intent: 'Run query', 'Execute DAX', 'Test DAX' -> Tool: `dax_query_operations` (Operation: Execute)\n"



                "5. Intent: 'Column', 'Field', 'Attribute', 'Data type' -> Tool: `column_operations`\n"



                "6. Intent: 'RLS', 'Role', 'Security', 'Permissions', 'Access' -> Tool: `security_role_operations`\n"



                "7. Intent: 'Relationship', 'Join', 'Link', 'Connection' -> Tool: `relationship_operations`\n"



                "8. Intent: 'Calculation Group', 'Format string' -> Tool: `calculation_group_operations`\n"



                "9. Intent: 'shared M query', 'M parameter', 'Power Query parameter' -> Tool: `named_expression_operations` (Create needs name + expression + kind M/DAX). NEVER use it for tables — data tables ALWAYS go through `table_operations`.\n"



                "- DO NOT HALLUCINATE: Never guess or invent details. You MUST use tools to query the real Power BI model for every check.\n"



                "- NO FAKE UPDATES: NEVER claim you updated, created, or changed something in plain text. YOU CANNOT MODIFY THE MODEL WITH TEXT. YOU MUST OUTPUT A VALID TOOL CALL JSON to actually perform the action! If you don't output a tool call, nothing happens.\n"



                "- CONVERSE FIRST: Talk to the user normally, like a pair-programming partner in an IDE. Greet, explain, discuss, show what you found, and ask clarifying questions in plain text. You may READ freely (List/Get/Execute operations) to ground your answers in real data. But NEVER emit a write operation (Create/Update/Delete/Modify/Drop/Alter/Rename, or generate_semantic_model) unless the user explicitly asked you to make that change. When in doubt, describe what you found and ask 'Want me to go ahead?' instead of acting on your own.\n"



                "- If a tool returns 'pendingApproval': True, it means a proposal was successfully sent to the user. Stop and just say 'I have proposed the changes for your approval.' Do NOT call any more tools.\n"



                "- FINAL RESPONSE: When you write the final text response to the user, DO NOT write any internal thoughts. Just directly answer the question.\n"



                "- READ-ONLY FIRST: If the user asks to inspect, count, list, or describe files/folders/tables (e.g. 'how many sales files are in this folder?'), call 'list_folder_files' to get the actual listing, report what you find from the result, and ASK the user before proposing or building anything. NEVER auto-create tables or auto-generate a model for an inspection question.\n"
                "\n"
                "- PLAIN-LANGUAGE MODEL SUMMARIES: When the user asks about connected models or wants a model overview, describe it in everyday, non-technical terms. Include: (a) the report/PBIX file name, (b) the tables inside the model, and (c) the key measures available. Do NOT use technical jargon like compatibility level, processing timestamps, estimated size, GUIDs, or internal model IDs. Example: 'You are connected to the Sales Report. It has 4 tables — Sales, Customers, Products, and Calendar — and 6 measures including Total Revenue and Profit Margin.'\n"



                "- SINGLE-TABLE COMBINES: When the user asks to combine/append a few files into ONE table, emit exactly ONE table_operations 'Create' proposal containing ONE definitions object with name + mExpression + columns together. NEVER emit duplicate definitions objects with the same name. NEVER call 'generate_semantic_model' for a single-table combine — that tool builds a whole multi-table model and opens the model preview, which is wrong for this task. NEVER use 'named_expression_operations' for tables either — named expressions cannot hold data tables. A single-table proposal opens in the code editor for review, which is the correct UX. If the source files are loose files on disk (not in the model yet), FIRST call 'read_file_headers' with their full paths to learn the real column names/types, then build the mExpression (Csv.Document or Excel.Workbook reads per file plus Table.Combine) and the columns array from that result. Use the EXACT 'delimiter' reported per file in the M-code (e.g. [Delimiter=\";\"] when it says so) — never guess it. NEVER propose a Create with only a name and no mExpression/columns. NEVER invent lineageTag/sourceLineageTag values (e.g. table names) — they must be GUIDs or omitted entirely.\n"



            )



            



            if target_agent == "dax_agent":



                agent_prompt = (



                    f"You are the DAX Agent. Your specialty is creating measures and DAX queries.{base_rules}\n"



                    "CRITICAL TABLE RULE: Every measure must belong to a Table. If a user asks to duplicate, modify, or create a measure based on an existing one, ALWAYS place it in the exact same Table as the original measure (use the List operation to find it if needed). However, if the user asks to create a completely NEW measure and forgets to specify the table name, DO NOT guess. Instead, politely ask the user: 'Which table would you like to place this measure in?'\n"



                    "MEASURE DUPLICATION & CONFLICT RULES:\n"



                    "1. NEVER create a measure if a measure with the same name already exists in the model. Power BI will fail. If the measure name exists, inform the user and ask to update it (operation='Update') or choose a new name.\n"



                    "2. If the user asks to create a measure with the exact same DAX formula as an existing measure, inform the user that the existing measure already performs this calculation, but proceed with proposing the new measure under their requested name."



                )



                allowed_tools = ["measure_operations", "database_operations", "dax_query_operations", "calculation_group_operations"]



            elif target_agent == "rls_agent":



                agent_prompt = (



                    f"You are the RLS Agent. Your specialty is Row-Level Security and Roles.{base_rules}\n"



                    "CRITICAL RLS RULE: To get the details or conditions of a security role, use operation='Get' and provide references=[{'name': 'RoleName'}]. Do NOT use 'GetPermissions' or 'permissionReferences' unless you also know the 'tableName', as 'tableName' is strictly required for permission references.\n"



                    "CRITICAL PERMISSION RULE: When updating or creating roles, ModelPermission values must be Title Case (e.g. 'Read', 'Administrator', 'None'). Do NOT use lowercase 'read'.\n"



                    "CRITICAL DAX RULE: When modifying a role's DAX filter expression, ALWAYS use operation='UpdatePermissions' with 'permissionDefinitions'. Do NOT use operation='Update' to rewrite the entire role definition!"



                )



                allowed_tools = ["security_role_operations", "database_operations", "table_operations"]



            else:



                agent_prompt = (



                    f"You are the Semantic Agent. Your specialty is overall Semantic Model architecture.{base_rules}\n"



                    "CRITICAL: When summarizing or analyzing a model, NEVER just dump raw database stats or metadata. To get the report/PBIX name, use `connection_operations` GetConnection or ListConnections to read the actual instance name. Then use `model_operations` Get for model identity, `table_operations` List for tables and `measure_operations` List for measures. Present the summary in plain, everyday language: the report/PBIX name, the tables inside, and the key measures. Do NOT use technical jargon like compatibility level, processing timestamps, estimated size, GUIDs, or internal model IDs. Example: 'You are connected to the Sales Report. It has 4 tables — Sales, Customers, Products, and Calendar — and 6 measures including Total Revenue and Profit Margin.'\n"



                    "CRITICAL TABLE CREATION RULE: When creating a Power Query/M-Code table (operation='Create'), the JSON table definition MUST include a top-level 'mExpression' field with the full M-Code. "



                    "Example of a correct create call:\n"



                    "{ \"operation\": \"Create\", \"definitions\": [{ \"name\": \"Sales\", \"mExpression\": \"let\\n  Source = Table.Combine({#\\\"Sales Data 2020\\\", #\\\"Sales Data 2021\\\", #\\\"Sales Data 2022\\\"})\\nin\\n  Source\" }] }\n"



                    "CRITICAL M-CODE SYNTAX RULE: In Power Query M, query/step names with spaces MUST be wrapped in #\"...\" (e.g., #\"Sales Data 2020\"). Never use bare identifiers like SalesData2020 for names with spaces â€” the engine will reject them.\n"



                    "TABLE.COMBINE ITEM RULE: Inside Table.Combine({...}), every item must be a table: a #\"Sales Data 2020\" style reference to a REAL model table (verify it exists with table_operations List first) or a Csv.Document/Excel.Workbook read for loose files. A bare \"display name\" string is just TEXT, and combining text crashes refresh with 'cannot convert the value ... to type Table'.\n"



                    "M QUOTING RULE: M strings use DOUBLE quotes only. NEVER write single-quoted literals. "
                    "Always File.Contents(\"..\") style double quotes and [Delimiter=\",\"] - single quotes are a parse error (Token Literal expected)."



                    "CRITICAL COMBINE RULE: When asked to combine or append tables, you MUST:\n"



                    "1. Use table_operations operation='Get' to read the M-Code of each source table first.\n"



                    "2. Inspect the returned partitionDetails[].expression to see the ACTUAL query/step names used.\n"



                    "3. Create the combined table using table_operations operation='Create' with a top-level 'mExpression' containing Table.Combine({...}) referencing those EXACT names with #\"...\" for any name containing spaces. If the sources are loose CSV files on disk, first call 'read_file_headers' for their full paths, then write an mExpression that reads each file and combines the promoted tables, e.g. let F1 = Csv.Document(File.Contents(\"C:\\data\\a.csv\"),[Delimiter=\",\", Encoding=1252, QuoteStyle=QuoteStyle.Csv]), P1 = Table.PromoteHeaders(F1), F2 = Csv.Document(File.Contents(\"C:\\data\\b.csv\"),[Delimiter=\",\", Encoding=1252, QuoteStyle=QuoteStyle.Csv]), P2 = Table.PromoteHeaders(F2), Combined = Table.Combine({P1, P2}) in Combined (use Excel.Workbook(File.Contents(\"path\"), null, true) plus Source{0}[Data] for .xlsx files). Always include the 'columns' array from the header results. NEVER combine raw Csv.Document outputs and promote once afterwards — PromoteHeaders EACH file first, or the other files' header rows become data rows and typed conversion fails. AND NEVER call Table.PromoteHeaders on the combined table afterwards — doing so promotes the first row of real data into column headers (e.g. '2020-01-01' becomes a column name) and causes Table.TransformColumnTypes to fail with 'The column <X> of the table wasn't found'. Feed the combined table directly into Table.TransformColumnTypes.\n"



                    "4. NEVER use 'measure_operations' for this task.\n"



                    "5. M CODE TYPE RULE: Inside M-Code, column types MUST be valid Power Query identifiers: type text, type number, type logical, type date, type datetime, type datetimezone, type duration, type binary. NEVER write type integer, type string, type int64, type double, type boolean (those are TOM/SQL names and crash evaluation with 'The type identifier is invalid'). Map integers AND decimals to type number, text-like to type text, true/false to type logical.\n"



                    "6. CHANGED TYPE STEP: Always end file-combine M-Code with a Changed Type step so Power Query shows real types instead of text, e.g. #\"Changed Type\" = Table.TransformColumnTypes(Combined, {{\"OrderDate\", type datetime}, {\"ProductKey\", type number}}) with one entry per column, then in #\"Changed Type\". NOTE THE DOUBLE BRACES around the pair list — Table.TransformColumnTypes takes exactly 2 args (table + list); single braces turn every pair into its own argument and refresh fails. Without this step every column stays text in Power Query.\n"



                    "5. When the user explicitly asks you to combine tables, propose the change with a 'Create' operation (which goes through user review) instead of only describing it. If they have NOT asked you to create anything, just discuss and ask before proposing.\n"



                    "RELATIONSHIP ANALYSIS PLAYBOOK: When the user asks about relationships (missing links, checking links between tables):\n"



                    "1. Call table_operations with operation='List' to learn the tables and their key columns.\n"



                    "2. Call relationship_operations with {\"request\": {\"operation\": \"List\"}} to learn the existing relationships. This is a read-only call — always do this before concluding anything about missing links.\n"



                    "3. Match fact-table key columns (CustomerKey, ProductKey, date keys) against dimension tables and propose genuinely missing links with relationship_operations 'Create' (goes through user review). VERIFY every column first with column_operations Get or table_operations List — NEVER guess ('potential X column' is forbidden). Always set BOTH fromCardinality ('Many' on the fact side) and toCardinality ('One' on the dimension side) explicitly, or the engine rejects the proposal with an opaque schema error.\n"



                    "4. NEVER narrate intent ('I would like to get/check...') — emit the calls above first, then write the analysis from their results.\n"



                )



                allowed_tools = ["table_operations", "column_operations", "relationship_operations", "database_operations", "model_operations", "connection_operations", "named_expression_operations", "generate_semantic_model", "list_folder_files", "read_file_headers"]



                



            agent_tools = [t for t in all_tools if t["function"]["name"] in allowed_tools]



                



            yield f"data: {{ \"type\": \"agent_handoff\", \"from\": \"manager\", \"to\": \"{target_agent}\", \"status\": \"executing\" }}\n\n"







            # Prepare sub-agent messages



            current_messages = [{"role": "system", "content": agent_prompt}]



            for m in server_conversation_history:



                if m["role"] != "system" and not m.get("content", "").startswith("[System Status]"):



                    clean_m = {k: v for k, v in m.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id"]}



                    if "content" not in clean_m:



                        clean_m["content"] = ""



                    if clean_m["role"] == "tool" and isinstance(clean_m.get("content"), str) and len(clean_m["content"]) > 15000:



                        clean_m["content"] = clean_m["content"][:15000] + "\n...[TRUNCATED TO SAVE TOKENS]"



                    current_messages.append(clean_m)



                    



            # Sub-Agent Execution Loop



            max_iterations = 15



            pending_measure_notice = None



            empty_retries = 0

            # One-shot guard against narrating intent without acting on it
            # (e.g. "I would like to get the relationships" with no tool call).
            reminded_about_relationships = False



            watchdog_fired = False

            proposal_sent_this_run = False
            _msg_yielded_this_run = False
            tool_calls_this_run = 0
            # One-shot per turn: salvage a tool call the model wrote as literal
            # <function=name>{...}</function> text instead of a real tool call.
            recovered_embedded_call = False
            # First validation blocker of the turn (table/relationship/named-
            # expression). Surfaced visibly if the turn ends with no proposal.
            _turn_blocker = None

            for iteration in range(max_iterations):



                def get_stream():



                    return call_llm(current_messages, agent_tools, settings, stream=True)



                



                try:



                    response_stream = await asyncio.to_thread(get_stream)



                except Exception as e:



                    traceback.print_exc(); yield f"data: {json.dumps({'type': 'message', 'content': f'LLM API Error: {str(e)}'})}\n\n"; _msg_yielded_this_run = True



                    break



                



                def get_next(iterator):



                    try:



                        return next(iterator)



                    except StopIteration:



                        return None



                        



                iterator = iter(response_stream)



                



                assistant_content = ""



                tool_calls_dict = {}



                proposal_sent_this_iter = False



                has_measure_err = False
                has_rel_err = False



                



                while True:



                    try:



                        chunk = await asyncio.to_thread(get_next, iterator)



                    except Exception as e:



                        traceback.print_exc(); yield f"data: {json.dumps({'type': 'message', 'content': f'LLM Stream Error: {str(e)}'})}\n\n"; _msg_yielded_this_run = True



                        break



                        



                    if chunk is None:



                        break



                        



                    if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta'):



                        delta = chunk.choices[0].delta



                        if hasattr(delta, 'content') and delta.content:



                            content = delta.content



                            if isinstance(content, list):



                                content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])



                            assistant_content += content



                            yield f"data: {json.dumps({'type': 'message', 'content': content})}\n\n"; _msg_yielded_this_run = True



                            



                        if hasattr(delta, 'tool_calls') and delta.tool_calls:



                            for tc in delta.tool_calls:



                                idx = tc.index



                                if idx not in tool_calls_dict:



                                    tool_calls_dict[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}



                                if tc.id:



                                    tool_calls_dict[idx]["id"] = tc.id



                                if tc.function.name:



                                    tool_calls_dict[idx]["function"]["name"] += tc.function.name



                                if tc.function.arguments:



                                    tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments



                



                msg_dict = {"role": "assistant", "content": assistant_content}



                



                if tool_calls_dict:



                    deduped_tcs = []



                    seen = set()



                    for idx, tc in sorted(tool_calls_dict.items()):



                        key = (tc["function"]["name"], tc["function"]["arguments"])



                        if key not in seen:



                            seen.add(key)



                            deduped_tcs.append(tc)



                    msg_dict["tool_calls"] = deduped_tcs



                




                # Salvage: the model sometimes writes its tool call as literal
                # <function=name>{...}</function> text instead of emitting a real
                # tool call (seen on follow-up turns). Recover the first valid one
                # into the normal tool pipeline instead of ending on narration.
                if "tool_calls" not in msg_dict and assistant_content.strip() and not recovered_embedded_call and not proposal_sent_this_run:
                    for _emb in re.finditer(r"<function=(\w+)>(.*?)</function>", assistant_content, re.DOTALL):
                        _emb_name, _emb_raw = _emb.group(1), _emb.group(2).strip()
                        try:
                            _emb_parsed = json.loads(_emb_raw)
                        except Exception:
                            continue
                        print(f"[{target_agent}] Recovered text-embedded <function={_emb_name}> call; routing into tool pipeline.")
                        recovered_embedded_call = True
                        current_messages.append(msg_dict)
                        msg_dict = {"role": "assistant", "content": None, "tool_calls": [
                            {"id": f"call_embedded_{uuid.uuid4().hex[:8]}", "type": "function",
                             "function": {"name": _emb_name, "arguments": _emb_raw}}]}
                        break
                current_messages.append(msg_dict)



                



                # If no tool calls, the agent is either done talking or stuck



                if "tool_calls" not in msg_dict or not msg_dict.get("tool_calls"):



                    if assistant_content.strip():


                        # End-of-turn watchdog: if this run produced nothing for review yet
                        # while the user asked for a concrete change, do not end on narration —
                        # give the model one guided extra iteration instead of stopping short.
                        _watch_verbs = ("create", "combin", "merg", "append", "generat", "build", "propos",
                                         "add", "updat", "delet", "remov", "drop", "alter", "renam",
                                         "make", "fix", "chang")
                        _recent_users = [str(m.get("content", "")) for m in server_conversation_history
                                         if isinstance(m, dict) and m.get("role") == "user"][-4:]
                        _latest_user = str(_recent_users[-1]) if _recent_users else ""
                        # A trailing "?" means the user asked for advice, not action — never force
                        # action on questions. (An explicit "yes" is handled via confirmed_this_turn.)
                        _write_wanted = confirmed_this_turn or (not _latest_user.rstrip().endswith("?") and (
                            any(any(v in u.lower() for v in _watch_verbs) for u in _recent_users[-1:]) or (
                                len(_latest_user.split()) <= 8 and any(any(v in u.lower() for v in _watch_verbs) for u in _recent_users))))
                        if not watchdog_fired and not proposal_sent_this_run and _write_wanted:
                            watchdog_fired = True
                            print(f"[{target_agent}] Turn ending with no proposal despite write intent — injecting watchdog directive.")
                            current_messages.append({
                                "role": "user",
                                "content": "Turn status: you have not produced anything for review yet even though the user's request is still open. If you have verified data supporting a concrete change, emit the required write tool call NOW (for a table: ONE table_operations Create proposal with name + mExpression + columns; for relationships: a Create proposal with fromTable/fromColumn/fromCardinality/toTable/toColumn/toCardinality). If there is genuinely nothing to change, write your final summary text instead. Do not ask another question and do not end with narration alone."
                            })

                            continue

                        # Plan-without-execution watchdog: the agent talks about its own next
                        # actions ("First, I will call...", "I would need to verify...") instead
                        # of taking them. Push one guided iteration using data already in context.
                        _self_intent = re.search(r"i (will|would|should|need to|want to|'ll|am going to|going to)|let me (first|now|also)|my next step", assistant_content, re.IGNORECASE)
                        _tech_talk = re.search(r"tool|operation|quer|\bcall|propos|m-code|mexpression|dax|headers?|columns?|relationship", assistant_content, re.IGNORECASE)
                        if (not watchdog_fired and not proposal_sent_this_run and _self_intent
                                and (tool_calls_this_run > 0 or _tech_talk)):
                            watchdog_fired = True
                            print(f"[{target_agent}] Turn ending on self-narration without action — injecting plan watchdog.")
                            current_messages.append({
                                "role": "user",
                                "content": "Turn status: you described your own next actions instead of taking them — even though everything you need is already in context above. NOW either emit the next tool call (for example column inspection with column_operations Get, or relationship_operations List) or write your FINAL findings/analysis from the data in hand. Do not describe plans, do not ask questions, do not stop mid-analysis."
                            })

                            continue


                        # Agent wrote text but only talked about checking relationships
                        # without calling the tool — remind once (with the exact call),
                        # then let it finish normally if it still does not call.
                        if (not reminded_about_relationships
                                and target_agent == "semantic_agent"
                                and re.search(r"relationship|table_operations|create\b|combin|analyz", assistant_content, re.IGNORECASE)
                                and re.search(r"I (would|will|need to|want to|'ll|am going to|going to)|let me|proceeding with|going ahead|need to (get|check|list|read|see|create|verify|analyz)", assistant_content, re.IGNORECASE)):
                            reminded_about_relationships = True
                            print(f"[{target_agent}] Text stated intent without a tool call — injecting one-shot reminder.")
                            current_messages.append({
                                "role": "user",
                                "content": "Reminder: do not just describe what you want to do — emit the tool call you need next. To inspect, call relationship_operations with {\"request\": {\"operation\": \"List\"}}. To propose (only with columns you already VERIFIED via column_operations Get or table_operations List, and BOTH fromCardinality and toCardinality set), emit the relationship_operations Create proposal. If you already have everything you need, write your final analysis instead."
                            })

                            continue







                        # Agent wrote text â€” it's done



                        print(f"[{target_agent}] Finished with text response (iteration {iteration+1})")



                        server_conversation_history.append({"role": "assistant", "content": assistant_content})



                        break



                    else:



                        empty_retries += 1



                        if empty_retries > 2:



                            # Give up after 2 retries



                            fallback = "I encountered difficulty processing the table data. The tables may be too large to combine in a single operation. Please try with fewer tables or simplify the request."



                            print(f"[{target_agent}] Giving up after {empty_retries} empty retries")



                            yield f"data: {json.dumps({'type': 'message', 'content': fallback})}\n\n"; _msg_yielded_this_run = True



                            server_conversation_history.append({"role": "assistant", "content": fallback})



                            break



                        # Empty response â€” the LLM choked (likely context too large)



                        print(f"[{target_agent}] Empty response on iteration {iteration+1}, injecting continuation prompt (retry {empty_retries})")



                        # Remove the empty assistant message we just appended



                        current_messages.pop()



                        # Inject a nudge to get the LLM to continue



                        current_messages.append({



                            "role": "user",



                            "content": "Please continue: either call the appropriate tool or write your final response to the user. Do not return an empty response."



                        })



                        continue



                if "tool_calls" in msg_dict and msg_dict["tool_calls"]:



                    for tc in msg_dict["tool_calls"]:



                        tool_calls_this_run += 1
                        t_name = tc["function"]["name"]



                        t_args_str = tc["function"]["arguments"]



                        t_id = tc["id"]



                        



                        # Log more for Create operations to debug mExpression vs daxExpression



                        if "Create" in t_args_str:



                            print(f"[{target_agent}] Tool call: {t_name}, FULL args: {t_args_str}")



                        else:



                            print(f"[{target_agent}] Tool call: {t_name}, args: {t_args_str[:200]}")



                        



                        try:



                            t_args = json.loads(t_args_str)



                        except:



                            t_args = {}







                        # Hard block: semantic_agent must NEVER use measure_operations



                        if target_agent == "semantic_agent" and t_name == "measure_operations":



                            block_msg = "ERROR: You are the Semantic Agent. You cannot use 'measure_operations'. To combine or create tables, use 'table_operations' with 'mExpression'. Retry with the correct tool."



                            print(f"[{target_agent}] BLOCKED measure_operations call!")



                            current_messages.append({"role": "assistant", "content": None, "tool_calls": [



                                {"id": t_id, "type": "function", "function": {"name": t_name, "arguments": t_args_str}}



                            ]})



                            current_messages.append({"role": "tool", "tool_call_id": t_id, "name": t_name, "content": block_msg})



                            yield f"data: {json.dumps({'type': 'tool_result', 'tool': t_name, 'result': block_msg})}\n\n"



                            continue



                            



                        try:



                            # Intercept writes so they require user approval



                            write_keywords = ["create", "add", "update", "modify", "set", "delete", "remove", "drop", "alter", "rename"]



                            operation = ""



                            if "request" in t_args and isinstance(t_args["request"], dict):



                                operation = str(t_args["request"].get("operation", ""))



                            elif "operation" in t_args:



                                operation = str(t_args.get("operation", ""))



                                



                            is_write = any(kw in t_name.lower() for kw in write_keywords) or any(kw in operation.lower() for kw in write_keywords)







                            if is_write and t_name == "measure_operations" and operation.lower() in ["create", "createorreplace"]:



                                measure_err, measure_notice = await validate_measure_creation(session, t_args)



                                if measure_err:



                                    # Remove the dangling assistant tool_call message so history stays clean



                                    if current_messages and current_messages[-1].get("role") == "assistant" and current_messages[-1].get("tool_calls"):



                                        current_messages.pop()



                                    yield f"data: {json.dumps({'type': 'message', 'content': measure_err})}\n\n"; _msg_yielded_this_run = True



                                    server_conversation_history.append({"role": "assistant", "content": measure_err})



                                    has_measure_err = True



                                    break



                                if measure_notice:



                                    pending_measure_notice = measure_notice







                            # Validate named_expression writes. DATA TABLES must go through
                            # table_operations — this tool is only for scalar shared M queries /
                            # DAX snippets and parameters, and it is not even offered for table work.
                            if is_write and t_name == "named_expression_operations" and operation.lower() in ["create", "createparameter", "update", "updateparameter"]:
                                from api.generate_semantic_model import heal_m_single_quotes
                                from api.generate_semantic_model import heal_m_type_identifiers_in_mexpression
                                from api.generate_semantic_model import repair_transformcolumntypes_shape
                                nx_defs = t_args.get("request", {}).get("definitions", []) if "request" in t_args else t_args.get("definitions", [])
                                nx_err = None
                                for nx_def in nx_defs:
                                    if not isinstance(nx_def, dict):
                                        continue
                                    _nx_expr = nx_def.get("expression")
                                    if not _nx_expr:
                                        nx_err = ("ERROR: named expression has no expression. A named expression MUST include its M or DAX expression. " +
                                                  "If you are trying to create a DATA TABLE (rows and columns, Table.Combine, Csv.Document), do NOT use named_expression_operations. " +
                                                  "Use table_operations Create with ONE definitions object containing name + mExpression + columns instead.")
                                        break
                                    if any(_kw in str(_nx_expr) for _kw in ("Table.Combine", "Csv.Document", "Excel.Workbook", "Table.PromoteHeaders", "Table.TransformColumnTypes")):
                                        nx_err = ("ERROR: that expression builds a DATA TABLE — named expressions cannot hold tables. " +
                                                  "Use table_operations Create with ONE definitions object containing name + mExpression + columns instead. " +
                                                  "Read loose file schemas first with read_file_headers if needed.")
                                        break
                                if not nx_err:
                                    for nx_def in nx_defs:
                                        if isinstance(nx_def, dict) and isinstance(nx_def.get("expression"), str):
                                            if str(nx_def.get("kind", "M")).strip().lower() != "dax":
                                                _nx_expr = heal_m_single_quotes(nx_def["expression"])
                                                _nx_expr = heal_m_type_identifiers_in_mexpression(_nx_expr)
                                                _nx_expr = repair_transformcolumntypes_shape(_nx_expr)
                                                if _nx_expr != nx_def["expression"]:
                                                    nx_def["expression"] = _nx_expr
                                                    tc["function"]["arguments"] = json.dumps(t_args)
                                if nx_err:
                                    current_messages.append({"role": "tool", "tool_call_id": tc["id"], "name": t_name, "content": nx_err})
                                    server_conversation_history.append({"role": "assistant", "content": nx_err})
                                    if _turn_blocker is None:
                                        _turn_blocker = nx_err
                                    yield f"data: {json.dumps({'type': 'thought_chunk', 'content': nx_err + chr(10) + chr(10)})}\n\n"
                                    break




                                



                            if is_write and t_name == "table_operations" and target_agent == "semantic_agent":
                                if operation.lower() == "create":
                                    try:
                                        t_args = normalize_table_create_request(t_args)
                                        tc["function"]["arguments"] = json.dumps(t_args)
                                    except Exception as norm_err:
                                        print(f"[{target_agent}] normalize_table_create_request FAILED: {norm_err}")
                                table_err = None
                                if "request" in t_args:
                                    defs = t_args.get("request", {}).get("definitions", [])
                                else:
                                    defs = t_args.get("definitions", [])
                                name_only_idx = None
                                expr_only_idx = None
                                for i, t_def in enumerate(defs):
                                    if not isinstance(t_def, dict):
                                        continue
                                    if "daxExpression" in t_def and t_def["daxExpression"]:
                                        table_err = ("ERROR: You provided 'daxExpression' for a table. You MUST use 'mExpression' (Power Query M-Code) instead. Retry with mExpression containing Table.Combine().")
                                        break
                                    if operation.lower() == "create" and "name" in t_def and "partitionName" not in t_def and "roleName" not in t_def:
                                        if "mExpression" not in t_def and "partitions" not in t_def and "source" not in t_def:
                                            name_only_idx = i
                                    if "name" not in t_def:
                                        if "mExpression" in t_def or "source" in t_def:
                                            expr_only_idx = i
                                if table_err is None and name_only_idx is not None:
                                    if expr_only_idx is not None:
                                        merged_name = defs[name_only_idx].get("name", "")
                                        defs[name_only_idx]["mExpression"] = defs[expr_only_idx].get("mExpression") or defs[expr_only_idx].get("source")
                                        if not defs[name_only_idx].get("columns") and defs[expr_only_idx].get("columns"):
                                            defs[name_only_idx]["columns"] = defs[expr_only_idx].get("columns")
                                        del defs[expr_only_idx]
                                        tc["function"]["arguments"] = json.dumps(t_args)
                                        print(f"[{target_agent}] Auto-merged split definition for '{merged_name}' into a single object.")
                                    else:
                                        table_err = ("ERROR: Missing 'mExpression' in the table definition that has 'name'. The definitions array must contain ONE object per table that has BOTH fields together, e.g. { \"name\": \"Sales Data\", \"mExpression\": \"let ... in ...\" }. If the source data lives in files on disk, FIRST call 'read_file_headers' with their full paths to learn the schemas, then write the mExpression plus the 'columns' array.")
                                if table_err is None and operation.lower() == "create":
                                    seen_names = set()
                                    for _d in defs:
                                        if not isinstance(_d, dict):
                                            continue
                                        if not _d.get("name"):
                                            continue
                                        _n = str(_d.get("name"))
                                        if _n in seen_names:
                                            table_err = ("ERROR: The definitions array contains duplicate entries for table '" + _n + "'. Send exactly ONE object per table with name + mExpression + columns together \u2014 never repeat the same table name.")
                                            break
                                        seen_names.add(_n)
                                if table_err is None and operation.lower() == "create":
                                    from api.generate_semantic_model import validate_combine_sources
                                    for _vd in defs:
                                        if not isinstance(_vd, dict):
                                            continue
                                        if not isinstance(_vd.get("mExpression"), str):
                                            continue
                                        _src_err = await validate_combine_sources(session, current_messages, _vd.get("mExpression"))
                                        if _src_err:
                                            table_err = _src_err
                                            break
                                if table_err is None and operation.lower() == "create":
                                    from api.generate_semantic_model import count_file_reads_and_promotes
                                    for _vd in defs:
                                        if not isinstance(_vd, dict):
                                            continue
                                        if not isinstance(_vd.get("mExpression"), str):
                                            continue
                                        _n_reads, _n_promotes = count_file_reads_and_promotes(_vd.get("mExpression"))
                                        if _n_reads > 0 and _n_promotes < _n_reads:
                                            table_err = ("ERROR: the M-Code reads %d file(s) but promotes headers only %d time(s). " % (_n_reads, _n_promotes) +
                                                         "PromoteHeaders EACH file right after its Csv.Document/Excel.Workbook read and only then Table.Combine the promoted tables — otherwise the other files’ header rows become data rows and typed conversion fails at refresh.")
                                            break
                                        if _n_reads > 0 and _n_promotes > _n_reads and "Table.Combine" in _vd.get("mExpression"):
                                            from api.generate_semantic_model import heal_redundant_promote_headers
                                            healed = heal_redundant_promote_headers(_vd.get("mExpression"))
                                            if healed != _vd.get("mExpression"):
                                                _vd["mExpression"] = healed
                                            else:
                                                table_err = ("ERROR: Redundant Table.PromoteHeaders detected. Do NOT call Table.PromoteHeaders on the combined table if the source files were already promoted — this promotes the first row of real data into column headers. Pass the combined table directly to Table.TransformColumnTypes.")
                                                break
                                if table_err is None and operation.lower() == "create":
                                    from api.generate_semantic_model import find_missing_source_files
                                    for _vd in defs:
                                        if not isinstance(_vd, dict):
                                            continue
                                        if not isinstance(_vd.get("mExpression"), str):
                                            continue
                                        _missing_files = find_missing_source_files(_vd.get("mExpression"))
                                        if _missing_files:
                                            table_err = ("ERROR: the M-Code references file(s) that do not exist on this machine: " + ", ".join(_missing_files) +
                                                         ". Fix the paths (or confirm the files are in place) before proposing \u2014 a table built on missing files can never refresh.")
                                            break
                                if table_err is None and operation.lower() == "create":
                                    for _d in defs:
                                        if not isinstance(_d, dict):
                                            continue
                                        if not _d.get("mExpression"):
                                            continue
                                        if _d.get("name"):
                                            continue
                                        table_err = ("ERROR: One table definition has an 'mExpression' but no 'name'. Put BOTH in a single object, e.g. { \"name\": \"Sales\", \"mExpression\": \"let ... in ...\", \"columns\": [...] }.")
                                        break
                                if table_err is None:
                                    try:
                                        for t_def in defs:
                                            if not isinstance(t_def, dict):
                                                continue
                                            mexpr = ""
                                            _raw_m = t_def.get("mExpression", "")
                                            if isinstance(_raw_m, str):
                                                mexpr = _raw_m
                                            if operation.lower() == "create" and "mExpression" in t_def and t_def.get("mExpression") and ("columns" not in t_def or not t_def.get("columns")):
                                                combine_match = re.search(r"Table\.Combine\s*\(\s*\{([^}]+)\}\s*\)", mexpr)
                                                if combine_match:
                                                    table_refs_str = combine_match.group(1)
                                                    source_table_names = []
                                                    for _m in re.finditer(r'#\"([^\"]+)\"', table_refs_str):
                                                        _cand = _m.group(1)
                                                        if not _cand:
                                                            continue
                                                        if any(_ch in _cand for _ch in ("\\", "/", ":")):
                                                            continue
                                                        source_table_names.append(_cand)
                                                    bare_scan = re.sub(r'"[^"]*"', "", table_refs_str)
                                                    bare_scan = re.sub(r"'[^']*'", "", bare_scan)
                                                    for _tok in re.split(r"[,\s]+", bare_scan):
                                                        _t = _tok.strip().strip("'")
                                                        if not _t:
                                                            continue
                                                        if not re.fullmatch(r"[A-Za-z_]\w*", _t):
                                                            continue
                                                        source_table_names.append(_t)
                                                    print(f"[{target_agent}] Detected source tables in mExpression: {source_table_names}")
                                                    columns_by_table = {}
                                                    for msg in current_messages:
                                                        if msg.get("role") != "tool":
                                                            continue
                                                        if msg.get("name") != "table_operations":
                                                            continue
                                                        try:
                                                            content = msg.get("content", "")
                                                            if not isinstance(content, str) or not content.strip():
                                                                continue
                                                            tool_result = json.loads(content)
                                                            results = tool_result.get("results", tool_result.get("data", []))
                                                            if not isinstance(results, list):
                                                                continue
                                                            for res in results:
                                                                data = res.get("data", res) if isinstance(res, dict) else res
                                                                if not isinstance(data, dict):
                                                                    continue
                                                                tbl_name = data.get("name", "")
                                                                matched = False
                                                                for src_name in source_table_names:
                                                                    norm_src = src_name.replace(" ", "").lower()
                                                                    norm_tbl = tbl_name.replace(" ", "").lower()
                                                                    if norm_src == norm_tbl:
                                                                        matched = True
                                                                        break
                                                                if not matched:
                                                                    continue
                                                                cols = data.get("columns", [])
                                                                if not cols:
                                                                    continue
                                                                columns_by_table[tbl_name] = cols
                                                        except Exception:
                                                            continue
                                                    if columns_by_table:
                                                        first_cols = next(iter(columns_by_table.values()))
                                                        if first_cols:
                                                            t_def["columns"] = first_cols
                                                            tc["function"]["arguments"] = json.dumps(t_args)
                                                            print(f"[{target_agent}] Auto-injected {len(first_cols)} columns from matched source tables into '{t_def.get('name')}'")
                                                        else:
                                                            table_err = "ERROR: Source tables found but have no column definitions."
                                                    else:
                                                        fallback_cols = None
                                                        for msg in current_messages:
                                                            if msg.get("role") != "tool":
                                                                continue
                                                            if msg.get("name") != "read_file_headers":
                                                                continue
                                                            try:
                                                                hcontent = msg.get("content", "")
                                                                if not isinstance(hcontent, str) or not hcontent.strip():
                                                                    continue
                                                                hdata = json.loads(hcontent)
                                                                for hf in hdata.get("files", []):
                                                                    if not isinstance(hf, dict):
                                                                        continue
                                                                    if not hf.get("success"):
                                                                        continue
                                                                    if not hf.get("file"):
                                                                        continue
                                                                    if hf.get("file") not in mexpr:
                                                                        continue
                                                                    if not hf.get("columns"):
                                                                        continue
                                                                    fallback_cols = hf.get("columns")
                                                                    break
                                                                if fallback_cols:
                                                                    break
                                                            except Exception:
                                                                continue
                                                        if not fallback_cols:
                                                            for msg in current_messages:
                                                                if msg.get("role") != "tool":
                                                                    continue
                                                                if msg.get("name") != "table_operations":
                                                                    continue
                                                                try:
                                                                    content = msg.get("content", "")
                                                                    if not isinstance(content, str) or not content.strip():
                                                                        continue
                                                                    tool_result = json.loads(content)
                                                                    results = tool_result.get("results", tool_result.get("data", []))
                                                                    if not isinstance(results, list):
                                                                        continue
                                                                    for res in results:
                                                                        data = res.get("data", res) if isinstance(res, dict) else res
                                                                        if not isinstance(data, dict):
                                                                            continue
                                                                        cols = data.get("columns", [])
                                                                        if not cols:
                                                                            continue
                                                                        fallback_cols = cols
                                                                        break
                                                                    if fallback_cols:
                                                                        break
                                                                except Exception:
                                                                    continue
                                                        if fallback_cols:
                                                            t_def["columns"] = fallback_cols
                                                            tc["function"]["arguments"] = json.dumps(t_args)
                                                            print(f"[{target_agent}] Auto-injected {len(fallback_cols)} columns from prior Get response (fallback) into '{t_def.get('name')}'")
                                                        else:
                                                            table_err = ("ERROR: When creating a table using 'mExpression', you MUST explicitly provide the 'columns' array. No source table columns could be determined. Please include columns like [{\"name\": \"OrderDate\", \"dataType\": \"dateTime\"}, ...].")
                                                else:
                                                    table_err = ("ERROR: When creating a table using 'mExpression', you MUST explicitly provide the 'columns' array (e.g. [{\"name\": \"ID\", \"dataType\": \"int64\"}, ...]). The schema cannot be inferred automatically by the engine.")
                                            known_table_names = set()
                                            for msg in current_messages:
                                                if msg.get("role") != "tool":
                                                    continue
                                                if msg.get("name") != "table_operations":
                                                    continue
                                                try:
                                                    content = msg.get("content", "")
                                                    if not isinstance(content, str) or not content.strip():
                                                        continue
                                                    tool_result = json.loads(content)
                                                    results = tool_result.get("results", tool_result.get("data", []))
                                                    if not isinstance(results, list):
                                                        continue
                                                    for res in results:
                                                        data = res.get("data", res) if isinstance(res, dict) else res
                                                        if not isinstance(data, dict):
                                                            continue
                                                        tbl_name = data.get("name", "")
                                                        if tbl_name:
                                                            known_table_names.add(tbl_name)
                                                except Exception:
                                                    continue
                                            try:
                                                for known_name in known_table_names:
                                                    if " " not in known_name:
                                                        continue
                                                    bare_name = known_name.replace(" ", "")
                                                    if bare_name and (bare_name in mexpr) and ((f'#\"{known_name}\"') not in mexpr):
                                                        table_err = ("ERROR: M-Code references '" + bare_name + "' but the actual table name is '" + known_name +
                                                                     "' (with spaces). In Power Query M, names with spaces MUST be wrapped in #\"...\" \u2014 use #\"" + known_name +
                                                                     "\" instead. Fix your Table.Combine to reference #\"" + known_name + "\").")
                                                        print(f"[{target_agent}] M-CODE VALIDATION FAILED: {table_err}")
                                                        break
                                            except Exception as val_err2:
                                                print(f"[{target_agent}] M-Code reference validation FAILED: {val_err2}")
                                                continue
                                    except Exception as val_err:
                                        print(f"[{target_agent}] table_operations validation FAILED: {val_err}")
                                if table_err:
                                    if _turn_blocker is None:
                                        _turn_blocker = table_err
                                    current_messages.append({"role": "tool", "tool_call_id": tc["id"], "name": t_name, "content": table_err})
                                    server_conversation_history.append({"role": "assistant", "content": table_err})
                                    yield f"data: {json.dumps({'type': 'thought_chunk', 'content': table_err + chr(10) + chr(10)})}\n\n"
                                    break
                            if is_write and t_name == "relationship_operations" and operation.lower() in ("create", "createorreplace", "update"):
                                from api.main import validate_relationship_definitions
                                if "request" in t_args:
                                    _rdefs = t_args.get("request", {}).get("definitions", [])
                                else:
                                    _rdefs = t_args.get("definitions", [])
                                # Auto-inject standard cardinalities when the LLM omits them.
                                # The engine always requires both; Many→One is the universal
                                # fact-to-dimension convention.
                                if isinstance(_rdefs, list):
                                    for _d in _rdefs:
                                        if isinstance(_d, dict):
                                            if not _d.get("fromCardinality"):
                                                _d["fromCardinality"] = "Many"
                                            if not _d.get("toCardinality"):
                                                _d["toCardinality"] = "One"
                                    # Propagate fixed defs back into t_args
                                    if "request" in t_args and isinstance(t_args["request"], dict):
                                        t_args["request"]["definitions"] = _rdefs
                                    else:
                                        t_args["definitions"] = _rdefs
                                _rel_errors = await validate_relationship_definitions(session, _rdefs)
                                if _rel_errors:
                                    _rel_err = "ERROR: relationship proposal invalid \u2014 " + " | ".join(_rel_errors) + ". Fix the definitions (verify table/column names live, set fromCardinality 'Many' on the fact side and toCardinality 'One' on the dimension side) and call again."
                                    current_messages.append({"role": "tool", "tool_call_id": tc["id"], "name": t_name, "content": _rel_err})
                                    if _turn_blocker is None:
                                        _turn_blocker = _rel_err
                                    server_conversation_history.append({"role": "assistant", "content": _rel_err})
                                    yield f"data: {json.dumps({'type': 'thought_chunk', 'content': _rel_err + chr(10) + chr(10)})}\n\n"
                                    has_rel_err = True
                                    break
                            if is_write:
                                yield f"data: {json.dumps({'type': 'tool_start', 'tool': t_name + ' [BLOCKED]'})}\n\n"
                                _split_defs = None
                                if t_name == "relationship_operations" and operation.lower() in ("create", "createorreplace", "update"):
                                    if "request" in t_args:
                                        _maybe_defs = t_args.get("request", {}).get("definitions", [])
                                    else:
                                        _maybe_defs = t_args.get("definitions", [])
                                    if isinstance(_maybe_defs, list) and len(_maybe_defs) > 1:
                                        _split_defs = _maybe_defs
                                if _split_defs is None:
                                    _split_defs = [None]
                                for _split_idx, _split_def in enumerate(_split_defs):
                                    proposal_id = str(uuid.uuid4())
                                    if _split_def is None:
                                        _split_args = t_args
                                    else:
                                        _split_args = {"request": {"operation": operation, "definitions": [_split_def]}}
                                        if isinstance(t_args.get("request"), dict) and "options" in t_args["request"]:
                                            _split_args["request"]["options"] = t_args["request"]["options"]
                                    proposals[proposal_id] = {"tool_name": t_name, "args": _split_args, "status": "pending", "original_state": None, "operation": operation}
                                    proposal_payload = {"type": "proposal", "id": proposal_id, "tool": t_name, "args": _split_args}
                                    yield f"data: {json.dumps(proposal_payload)}\n\n"
                                proposal_sent_this_iter = True
                                proposal_sent_this_run = True
                                tool_result_content = json.dumps({"success": True, "pendingApproval": True, "message": "Write operation is waiting for user approval. Do not execute it again."})
                            elif t_name == "generate_semantic_model":
                                from api.generate_semantic_model import generate_semantic_model
                                folder_path = t_args.get("folder_path", "")
                                yield f"data: {json.dumps({'type': 'thought_chunk', 'content': f'Scanning folder {folder_path} and generating model preview...'})}\n\n"
                                result_data = await asyncio.to_thread(generate_semantic_model, folder_path, settings)
                                yield f"data: {json.dumps({'type': 'generation_preview', 'schema': result_data['schema'], 'folder_path': result_data['folder_path'], 'csv_files': result_data['csv_files']})}\n\n"
                                tool_result_content = f"Model generation preview sent to the frontend successfully for {len(result_data['csv_files'])} files. I should ask the user if they'd like to review the generated preview in the center panel."
                            elif t_name == "list_folder_files":
                                from api.generate_semantic_model import list_folder_files
                                folder_path = t_args.get("folder_path", "")
                                yield f"data: {json.dumps({'type': 'thought_chunk', 'content': f'Listing files in {folder_path}...'})}\n\n"
                                list_data = await asyncio.to_thread(list_folder_files, folder_path)
                                tool_result_content = json.dumps(list_data)
                            elif t_name == "read_file_headers":
                                from api.generate_semantic_model import read_file_headers
                                file_paths = t_args.get("file_paths", [])
                                yield f"data: {json.dumps({'type': 'thought_chunk', 'content': 'Reading file headers...'})}\n\n"
                                headers_data = await asyncio.to_thread(read_file_headers, file_paths)
                                tool_result_content = json.dumps(headers_data)
                            else:
                                yield f"data: {json.dumps({'type': 'tool_start', 'tool': t_name})}\n\n"
                                t_result = await session.call_tool(t_name, t_args)
                                tool_result_content = t_result.content[0].text if t_result.content else "Success"
                        except Exception as e:
                            traceback.print_exc()
                            yield f"data: {json.dumps({'type': 'tool_error', 'error': str(e)})}\n\n"
                            tool_result_content = f"Error calling tool {t_name}: {str(e)}"
                        if isinstance(tool_result_content, str) and len(tool_result_content) > 8000:
                            tool_result_content = tool_result_content[:8000] + "\n...[TRUNCATED TO SAVE TOKENS]"
                        current_messages.append({"role": "tool", "tool_call_id": t_id, "name": t_name, "content": tool_result_content})
                    if has_measure_err or has_rel_err:
                        break
                    if proposal_sent_this_iter:
                        summary_prompt = "The write operation proposal has been sent to the user for review. Please provide a brief, friendly confirmation message (1-2 sentences) summarizing what you proposed, without calling any more tools."
                        if pending_measure_notice:
                            summary_prompt += f"\nIMPORTANT NOTICE TO INCLUDE: {pending_measure_notice}"
                        current_messages.append({"role": "user", "content": summary_prompt})
                        def get_summary_stream():
                            return call_llm(current_messages, [], settings, stream=True)
                        try:
                            summary_stream = await asyncio.to_thread(get_summary_stream)
                        except Exception as e:
                            traceback.print_exc()
                            yield f"data: {json.dumps({'type': 'message', 'content': 'Summary LLM API Error: ' + str(e)})}\n\n"; _msg_yielded_this_run = True
                            break
                        summary_iterator = iter(summary_stream)
                        summary_content = ""
                        while True:
                            try:
                                chunk = await asyncio.to_thread(get_next, summary_iterator)
                            except Exception as e:
                                traceback.print_exc()
                                yield f"data: {json.dumps({'type': 'message', 'content': 'Summary LLM Stream Error: ' + str(e)})}\n\n"; _msg_yielded_this_run = True
                                break
                            if chunk is None:



                                break



                            if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta'):



                                delta = chunk.choices[0].delta



                                if hasattr(delta, 'content') and delta.content:



                                    content = delta.content



                                    if isinstance(content, list):



                                        content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])



                                    yield f"data: {json.dumps({'type': 'message', 'content': content})}\n\n"; _msg_yielded_this_run = True



                                    summary_content += content



                        if not summary_content.strip():



                            summary_content = "I have proposed the changes for your review. Please check the proposal card below to review and approve or reject."



                            if pending_measure_notice:



                                summary_content += f"\n\n{pending_measure_notice}"



                            yield f"data: {json.dumps({'type': 'message', 'content': summary_content})}\n\n"; _msg_yielded_this_run = True



                        server_conversation_history.append({"role": "assistant", "content": summary_content})



                        break



                else:



                    if not assistant_content.strip():



                        assistant_content = "I have reviewed your request. Please let me know if you would like me to make any changes to the model."



                        yield f"data: {json.dumps({'type': 'message', 'content': assistant_content})}\n\n"; _msg_yielded_this_run = True



                    server_conversation_history.append({"role": "assistant", "content": assistant_content})



                    break











                    










            # A validation blocker (table/relationship/named-expression) stopped
            # this turn with no proposal: state it plainly so the user knows what
            # to fix, instead of ending on narration alone.
            if _turn_blocker is not None and not proposal_sent_this_run:
                _blocker_note = f"I couldn't propose the change yet \u2014 {_turn_blocker}"
                yield f"data: {json.dumps({'type': 'message', 'content': _blocker_note})}\n\n"; _msg_yielded_this_run = True
                server_conversation_history.append({"role": "assistant", "content": _blocker_note})



            # Last-resort visibility: never end a turn in total silence. If no
            # proposal went out and no message/error was ever yielded, say so
            # honestly instead of leaving the user staring at nothing.
            if not proposal_sent_this_run and not _msg_yielded_this_run:
                _tools_seen = sorted({str(m.get("name")) for m in current_messages
                                     if isinstance(m, dict) and m.get("role") == "tool" and m.get("name")})
                if _tools_seen:
                    _fb = ("I worked through " + ", ".join(_tools_seen) + " but couldn't assemble that "
                           "into a result. Please try rephrasing the request, and I can have another go.")
                else:
                    _fb = ("I couldn't make progress on that just now. Please try rephrasing the request, "
                           "and I can have another go.")
                yield f"data: {json.dumps({'type': 'message', 'content': _fb})}\n\n"
                server_conversation_history.append({"role": "assistant", "content": _fb})
                _msg_yielded_this_run = True

            print(f"[TURN] done: proposal_sent={proposal_sent_this_run} msg_yielded={_msg_yielded_this_run} tool_calls={tool_calls_this_run}", flush=True)

            # Handoff back



            yield f"data: {{ \"type\": \"agent_handoff\", \"from\": \"{target_agent}\", \"to\": \"manager\", \"status\": \"complete\" }}\n\n"



            yield "data: [DONE]\n\n"







        except Exception as e:



            traceback.print_exc(); yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"; _msg_yielded_this_run = True












    return StreamingResponse(event_generator(), media_type="text/event-stream")




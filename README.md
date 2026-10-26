# Power BI IDE

An AI-powered development studio and modeling assistant for Power BI Desktop. Build, refine, and orchestrate semantic models, DAX measures, Power Query transformations, and relationships directly from a modern developer interface.

---

## Requirements

- **Windows 10/11** (64-bit)
- **Power BI Desktop** running with an open model (`.pbix` or `.pbip`)
- **Internet connection** (for first-time setup only)
- **AI Model Access:** An API key for Databricks, OpenAI, Anthropic, or Groq (configured directly inside the app UI)

> **Note:** You do NOT need Python or Node.js pre-installed. The setup script configures an isolated environment automatically.

---

## Quick Start

1. **Set up the environment (One-time, ~2 min):**
   * Double-click `setup.bat`. This automatically provisions an isolated Python 3.12 environment with pinned dependencies.
2. **Launch the application:**
   * Double-click `run.bat`. Your browser will open automatically at `http://localhost:8000`.
3. **Configure your AI Provider:**
   * Click the **Settings icon (⚙)** in the bottom-left corner of the app.
   * Select your preferred provider (Databricks, OpenAI, Anthropic, or Groq) and paste your token / API key.
   * Settings are saved locally in `config.json` — **no `.env` file required!**

---

## Architecture & Features

- **Multi-Agent Orchestration:** Specialized AI agents handle TMDL, DAX formulas, Power Query (M), semantic relationships, and security roles.
- **Model Context Protocol (MCP):** Connects directly to running local Power BI Analysis Services instances for real-time schema inspection, query execution, and transactional modifications.
- **In-Browser Code & Model Preview:** Monaco-based code editors with live DAX and M-code healing, TMDL syntax highlighting, and visual relationship graphs.
- **Safe Review Workflow:** Proposes changes for human review (accept / reject / edit) before committing them to your active Power BI model.

---

## Folder Structure

```
PBI IDE/
├── api/                # FastAPI backend & Multi-Agent orchestration
│   ├── main.py         # Application entry point & endpoints
│   ├── multi_agent.py  # Agent coordination, prompts & validation
│   ├── mcp_client.py   # MCP communication with Power BI
│   └── ...
├── frontend/           # Modern React + Vite developer studio UI
│   ├── src/            # Components, state management, and styling
│   └── public/         # Static assets and icons
├── server/             # Power BI Modeling MCP server executable & DLLs
├── config.json         # Local user settings (AI providers, API keys)
├── requirements.txt    # Pinned Python dependencies
├── setup.bat           # Automated environment setup script
├── run.bat             # Application build & launch script
└── README.md           # Documentation
```

---

## Troubleshooting

| Issue | Resolution |
| :--- | :--- |
| **"Python not found" during setup** | Ensure you have an active internet connection; `setup.bat` will download a portable Python 3.12 automatically. |
| **"MCP server not found"** | Verify that `server\powerbi-modeling-mcp.exe` exists in the `server\` directory. |
| **Port 8000 already in use** | Stop any existing instance via `Ctrl + C` in its command window, or terminate previous uvicorn processes. |
| **Model not detected** | Ensure Power BI Desktop is actively running with a report or dataset open before launching. |
| **Reset to clean state** | Delete `venv/` and `frontend/dist/`, then re-run `setup.bat` and `run.bat`. |

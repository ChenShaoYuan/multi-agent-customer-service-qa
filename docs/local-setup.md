# Local development setup

## Requirements

- Windows 10/11
- Git 2.45 or newer
- Python 3.11
- GitHub CLI 2.x

## Create the environment

PowerShell:

```powershell
cd D:\PTA\PTA1\multi-agent-customer-service-qa

# On this machine, use the installed interpreter directly because the current
# Python launcher still points to a Windows Store alias.
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv .venv

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Configure local secrets

```powershell
Copy-Item .env.example .env # First setup only; preserve an existing .env
```

Edit `.env` and provide `LLM_API_KEY` or `DASHSCOPE_API_KEY`. The `.env` file is ignored by Git and must not be committed. For the configured Qwen-compatible service see [model connection](model-connection.md).

## Validate the project

```powershell
python -m pytest
python -m ruff check .
```

Tests cover all four weeks and do not call an external LLM. MCP integration tests start a temporary HTTP service on localhost. Final validation and real-model results are in [Week 4](week4/evaluation-report.md).

## Git workflow

```powershell
git switch -c feature/week2-preflight
# Make changes, run tests, then commit and push the branch.
```

Use pull requests for mentor review so design and code changes remain visible and easy to discuss.

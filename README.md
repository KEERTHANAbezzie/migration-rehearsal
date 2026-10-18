# Migration Rehearsal

An evidence-first prototype for reviewing a proposed database schema migration before deployment.

## What it does
- Supports a small set of operations: rename a column, drop a column, and change a column type.
- Runs explicit checks against a sample schema and dependency inventory.
- Compares baseline findings with findings augmented by sample historical migration records.
- Displays the evidence and suggests validation checks.
- Optionally asks Gemini to explain the structured evidence when `GEMINI_API_KEY` is configured.
- Does not execute SQL or make production changes.

## Important limitations
- Bundled data is synthetic demonstration data.
- Dependency coverage is incomplete.
- Historical matching uses simple lexical rules, not embeddings or a semantic search engine.
- Findings are not calibrated risk probabilities and are not proof of real-world accuracy.
- AI explanations are advisory and must be verified.

## Run locally (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Run locally (Git Bash)
```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Enable Gemini
Set the key as an environment variable before launching the app. In Git Bash for the current terminal session:
```bash
export GEMINI_API_KEY="your-key-here"
python -m streamlit run app.py
```
Never commit API keys. The default model is `gemini-2.5-flash`; override with `GEMINI_MODEL` if needed and available to your account.

## Deploy to Google Cloud Run
1. Create/select a Google Cloud project and configure billing according to your needs.
2. Enable Cloud Run and Cloud Build APIs.
3. Install and authenticate Google Cloud CLI.
4. From this directory, deploy using the official Cloud Run source or container workflow. This repository includes a Dockerfile:
```bash
gcloud config set project YOUR_PROJECT_ID
gcloud run deploy migration-rehearsal --source . --region asia-south1 --allow-unauthenticated
```
Review costs and access settings before making the service public. Cloud Build may need permission to build the source. For secrets, configure `GEMINI_API_KEY` through Cloud Run environment/secret settings rather than committing it to source.

## Suggested demo
1. Select `Rename column` for `customers.customer_id`.
2. Show baseline dependencies (Billing API and reporting ETL).
3. Show the related historical case and its recorded validation test.
4. Explain that sample data is synthetic and the tool is a review assistant, not a database simulator.

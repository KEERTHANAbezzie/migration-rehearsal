import json
from pathlib import Path
import pandas as pd

def load_project_data(data_dir: Path):
    with open(data_dir / "schema.json", "r", encoding="utf-8") as f:
        schema = json.load(f)
    deps = pd.read_csv(data_dir / "dependencies.csv").fillna("")
    hist = pd.read_csv(data_dir / "historical_migrations.csv").fillna("")
    return {
        "schema": schema,
        "dependencies": deps.to_dict(orient="records"),
        "history": hist.to_dict(orient="records")
    }

def analyze_migration(operation, table, column, new_name, new_type, data, use_history=True):
    target = f"{table}.{column}"
    baseline, historical = [], []
    deps = [d for d in data["dependencies"] if d["table"] == table and d["column"] == column]
    # Deterministic checks: each finding includes the row that triggered it.
    for d in deps:
        severity = d.get("severity", "Medium")
        if operation in ("Drop column", "Rename column"):
            title = f"{operation} may affect {d['dependent_system']}"
            explanation = f"The dependency inventory says {d['dependent_system']} references {target}. "
            if operation == "Rename column":
                explanation += f"Review whether it has been updated to use {table}.{new_name or '[new name]'}."
            else:
                explanation += "Removing the column may break this consumer unless it is updated or no longer needs the field."
            test = f"Run an integration/contract test for {d['dependent_system']} using the migration in a non-production environment."
            baseline.append({
                "title": title, "severity": severity, "explanation": explanation,
                "evidence": f"{d['dependent_system']} references {target}; dependency record: {d.get('reference','not specified')}",
                "test": test, "source": "dependencies.csv"
            })
        elif operation == "Change column type":
            title = f"Type change may affect {d['dependent_system']}"
            explanation = f"{d['dependent_system']} consumes {target}; verify its expected type, parsing, comparisons, and serialization."
            test = f"Test representative values and the consumer contract for {d['dependent_system']} after the type change to {new_type}."
            baseline.append({
                "title": title, "severity": severity, "explanation": explanation,
                "evidence": f"{d['dependent_system']} references {target}; dependency record: {d.get('reference','not specified')}",
                "test": test, "source": "dependencies.csv"
            })

    if operation == "Rename column" and (not new_name or new_name == column):
        baseline.append({
            "title": "New column name needs review", "severity": "Low",
            "explanation": "The new name is empty or unchanged, so the migration proposal may not represent an intended rename.",
            "evidence": f"Input operation={operation}; old={column}; new={new_name}",
            "test": "Confirm the intended old and new identifiers before reviewing downstream consumers.",
            "source": "input validation"
        })
    if operation == "Drop column":
        baseline.append({
            "title": "Data removal / rollback consideration", "severity": "Medium",
            "explanation": "Dropping a column may remove data or make rollback difficult if the value is not recoverable.",
            "evidence": f"Proposed operation: drop {target}",
            "test": "Confirm retention requirements, backup/restore strategy, and whether a staged deprecation is safer.",
            "source": "explicit migration rule"
        })
    if operation == "Change column type":
        baseline.append({
            "title": "Type conversion compatibility", "severity": "Medium",
            "explanation": f"Changing {target} to {new_type} may fail or change semantics for values that cannot be converted or that downstream consumers interpret differently.",
            "evidence": f"Proposed type change: {target} -> {new_type}",
            "test": "Run a conversion check against representative and boundary values; verify nulls, ranges, formats and application serialization.",
            "source": "explicit migration rule"
        })

    if operation == "Rename column":
        match_terms = ["rename", "column"]
    elif operation == "Drop column":
        match_terms = ["drop", "column"]
    else:
        match_terms = ["type", "column"]
    if use_history:
        for h in data["history"]:
            text = " ".join(str(h.get(k, "")) for k in ["operation", "table", "column", "summary", "outcome"]).lower()
            # Simple lexical match only; deliberately not presented as semantic similarity.
            if any(term in text for term in match_terms) and (
                h.get("operation","").lower() == operation.lower()
                or h.get("table","").lower() == table.lower()
                or h.get("column","").lower() == column.lower()
            ):
                historical.append({
                    "title": f"Related historical case: {h.get('case_id','unknown')}",
                    "severity": h.get("severity","Medium"),
                    "explanation": h.get("summary","Historical record matched the current operation or target."),
                    "evidence": f"Historical case {h.get('case_id','unknown')}; recorded outcome: {h.get('outcome','not recorded')}",
                    "test": h.get("validation_test","Review the historical case and create a targeted regression test."),
                    "source": "historical_migrations.csv"
                })

    # Avoid duplicate title collisions and clearly separate baseline from added history.
    enhanced = baseline + historical
    findings = enhanced
    checklist = [
        f"Confirm all consumers of {target} are represented in the dependency inventory",
        "Run migration in an isolated development or staging environment",
        "Test application integration/contract paths affected by this change",
        "Validate representative, boundary, null and legacy data values where applicable",
        "Confirm backup, rollback and recovery steps with the database owner",
        "Review historical cases and verify they apply to this system",
        "Obtain peer/database-owner review before production"
    ]
    return {
        "operation": operation,
        "target": target,
        "new_name": new_name if operation == "Rename column" else None,
        "new_type": new_type if operation == "Change column type" else None,
        "baseline": baseline,
        "historical_additions": historical,
        "enhanced": enhanced,
        "findings": findings,
        "checklist": checklist,
        "limitations": [
            "Bundled schema, dependency and historical records are synthetic demonstration data.",
            "Historical matching uses simple lexical rules, not embeddings or semantic search.",
            "Dependency inventory may be incomplete and cannot guarantee all consumers are discovered.",
            "No SQL is executed and no production system is changed.",
            "Gemini output, when configured, is advisory and must be checked against the evidence."
        ]
    }

def validate_ai_response(text):
    return bool(text and text.strip())

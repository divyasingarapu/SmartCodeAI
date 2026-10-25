
from finding_deduplicator import deduplicate_findings

findings = [
    {
        "type": "Security",
        "severity": "high",
        "line": 4,
        "message": "Potential security risk: eval() can execute dynamically supplied Python code.",
        "suggestion": "Avoid eval() with untrusted input.",
    },
    {
        "type": "Static Analysis (Bandit)",
        "severity": "medium",
        "line": 7,
        "message": "B307: Use of possibly insecure function - consider using safer ast.literal_eval.",
        "suggestion": "Use ast.literal_eval where appropriate.",
    },
    {
        "type": "Static Analysis (Bandit)",
        "severity": "high",
        "line": 9,
        "message": "B602: subprocess call with shell=True identified, security issue.",
        "suggestion": "Avoid shell=True.",
    },
    {
        "type": "Shell Command Injection Risk",
        "severity": "high",
        "line": 5,
        "message": "A subprocess call enables shell=True.",
        "suggestion": "Prefer shell=False.",
    },
]

for issue in deduplicate_findings(findings):
    print(
        issue["type"],
        "| Line:", issue.get("line"),
        "| Severity:", issue.get("severity"),
        "| Duplicates:", issue.get("duplicate_count"),
        "| Sources:", issue.get("sources"),
        "| Message:", issue.get("message"),
    )

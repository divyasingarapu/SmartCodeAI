from finding_deduplicator import deduplicate_findings

findings = [
    {
        "type": "Static Analysis (Bandit)",
        "severity": "high",
        "line": 7,
        "message": "B602: subprocess call with shell=True",
        "suggestion": "Avoid shell=True",
    },
    {
        "type": "Custom security scanner",
        "severity": "high",
        "line": 7,
        "message": "Shell command injection risk: shell=True",
        "suggestion": "Use shell=False",
    },
    {
        "type": "Static Analysis (Bandit)",
        "severity": "high",
        "line": 15,
        "message": "B602: subprocess call with shell=True",
        "suggestion": "Avoid shell=True",
    },
]

result = deduplicate_findings(findings)

print("Total findings:", len(result))

for item in result:
    print(
        f'Line {item["line"]}: {item["message"]} '
        f'| Sources: {item["sources"]} '
        f'| Duplicates: {item["duplicate_count"]}'
    )

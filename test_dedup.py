
from finding_deduplicator import deduplicate_findings

source_code = """
import requests
response = requests.get("https://example.com", verify=False)
"""

findings = [
    {
        "type": "Static Analysis",
        "line": 3,
        "severity": "medium",
        "message": "TLS certificate verification disabled.",
    },
    {
        "type": "Security scanner",
        "line": 3,
        "severity": "high",
        "message": "HTTPS request uses verify=False.",
    },
]

result = deduplicate_findings(
    findings,
    source_code=source_code,
    language="python",
)

for issue in result:
    print(issue)

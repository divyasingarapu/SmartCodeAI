
from security_scanner import scan_security

sample_code = """
import os
import subprocess
import yaml
import requests

password = os.getenv("APP_PASSWORD")
data = yaml.safe_load(untrusted_data)
response = requests.get(url, timeout=10)
subprocess.run(["echo", "hello"], check=True)
"""

findings = scan_security(sample_code, "python")

for finding in findings:
    print(
        f'{finding["severity"].upper():8} '
        f'Line {finding["line"]:>2} | '
        f'{finding["type"]}: {finding["message"]}'
    )

print(f"\nTotal findings: {len(findings)}")

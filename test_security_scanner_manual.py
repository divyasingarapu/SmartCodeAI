
from security_scanner import scan_security


sample_code = '''
import subprocess
import yaml
import requests
import hashlib

password = "RealisticExampleSecret456"
result = eval(user_input)
subprocess.run(user_command, shell=True)
data = yaml.load(untrusted_data)
response = requests.get(url, verify=False)
digest = hashlib.md5(data)
'''


findings = scan_security(sample_code, "python")

for finding in findings:
    print(
        f'{finding["severity"].upper():8} '
        f'Line {finding["line"]:>2} | '
        f'{finding["type"]}: {finding["message"]}'
    )

print(f"\nTotal findings: {len(findings)}")

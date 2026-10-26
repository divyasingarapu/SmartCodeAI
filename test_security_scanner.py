
from security_scanner import scan_security

sample_code = '''
import subprocess
import requests

password = "RealisticExampleSecret123"
result = eval(user_input)

subprocess.run(user_command, shell=True)

response = requests.get(
    "https://example.com",
    verify=False
)
'''

findings = scan_security(sample_code, "python")

if not findings:
    print("No security patterns detected.")
else:
    print("Security findings:")

    for finding in findings:
        print("-" * 50)
        print("Type:", finding["type"])
        print("Severity:", finding["severity"])
        print("Line:", finding["line"])
        print("Message:", finding["message"])
        print("Suggestion:", finding["suggestion"])


import unittest

from finding_deduplicator import deduplicate_findings


class DeduplicateFindingsTests(unittest.TestCase):

    def test_merges_eval_findings_from_different_scanners(self):
        findings = [
            {
                "type": "Static Analysis (Bandit)",
                "severity": "medium",
                "line": 7,
                "message": "B307: Use of possibly insecure function eval().",
                "suggestion": "Consider ast.literal_eval.",
            },
            {
                "type": "Dangerous Dynamic Execution",
                "severity": "high",
                "line": 7,
                "message": "Use of eval() can execute dynamically supplied code.",
                "suggestion": "Avoid evaluating untrusted input.",
            },
        ]

        result = deduplicate_findings(findings)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["severity"], "high")
        self.assertEqual(result[0]["duplicate_count"], 2)
        self.assertIn("Bandit", result[0]["sources"])
        self.assertIn("Custom security scanner", result[0]["sources"])

    def test_merges_shell_true_findings(self):
        findings = [
            {
                "type": "Static Analysis (Bandit)",
                "severity": "high",
                "line": 10,
                "message": "B602: subprocess call with shell=True identified.",
                "suggestion": "Avoid shell=True.",
            },
            {
                "type": "Shell Command Injection Risk",
                "severity": "high",
                "line": 10,
                "message": "A subprocess call enables shell=True.",
                "suggestion": "Use shell=False.",
            },
        ]

        result = deduplicate_findings(findings)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duplicate_count"], 2)

    def test_merges_hardcoded_secret_findings(self):
        findings = [
            {
                "type": "Static Analysis (Bandit)",
                "severity": "low",
                "line": 3,
                "message": "B105: Possible hardcoded password.",
                "suggestion": "Check the password.",
            },
            {
                "type": "Possible Hardcoded Secret",
                "severity": "high",
                "line": 3,
                "message": "A password appears to contain a literal value.",
                "suggestion": "Use an environment variable.",
            },
        ]

        result = deduplicate_findings(findings)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["severity"], "high")

    def test_keeps_different_issues_on_the_same_line(self):
        findings = [
            {
                "type": "Ruff",
                "severity": "medium",
                "line": 7,
                "message": "F821: Undefined name user_input.",
                "suggestion": "Define the variable.",
            },
            {
                "type": "Dangerous Dynamic Execution",
                "severity": "high",
                "line": 7,
                "message": "eval() can execute dynamic code.",
                "suggestion": "Avoid eval().",
            },
        ]

        result = deduplicate_findings(findings)

        self.assertEqual(len(result), 2)

    def test_removes_exact_duplicates(self):
        issue = {
            "type": "Ruff",
            "severity": "low",
            "line": 1,
            "message": "I001: Import block is unsorted.",
            "suggestion": "Sort imports.",
        }

        result = deduplicate_findings([issue, dict(issue)])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duplicate_count"], 2)

    def test_handles_exact_duplicates_without_line_numbers(self):
        issue = {
            "type": "Dangerous Dynamic Execution",
            "severity": "high",
            "line": None,
            "message": "eval() can execute dynamic code.",
            "suggestion": "Avoid eval().",
        }

        result = deduplicate_findings([issue, dict(issue)])

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

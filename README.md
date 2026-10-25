# SmartCode AI — Intelligent Code Review Platform

SmartCode AI is a Python-based code review platform designed to help developers identify potential code issues, inspect common security risks, review public GitHub repositories, and generate and run basic automated tests.

The project combines static code analysis, security checks, GitHub integration, and test-generation workflows in a web interface built with Flask.

## Features

### 1. Code Review
- Submit source code for analysis.
- Review supported Python and Java code.
- View reported issues, severity levels, line numbers, and suggested improvements.

### 2. Security Analysis
- Scan source code for selected security-risk patterns.
- Display findings alongside code-review results.
- Provide suggestions to help developers investigate potential vulnerabilities.

*Note: Static security checks are heuristic-based and cannot guarantee that code is secure.*

### 3. GitHub Repository Review
- Browse eligible Python files in public GitHub repositories.
- Review individual source files.
- Inspect file-level findings and suggested improvements.

### 4. Batch Code Review
- Select multiple Python files for analysis.
- Review findings across selected files.
- View summary statistics for reviewed files, failures, and severity levels.

### 5. Automated Test Generation
- Generate basic pytest test code for supported Python functions.
- View generated tests and the functions covered.
- Copy or download generated test files.

### 6. Test Execution
- Run generated tests and display execution results.
- View passed, failed, and skipped test counts.
- Inspect available error messages and test output.

**Security note:** The current test runner is a local prototype, not a secure sandbox. Do not run untrusted code or expose the test execution service publicly without implementing proper isolation and resource limits.

## Technology Stack

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, Jinja2 templates
- **Code Analysis:** Custom Python analysis modules
- **Security Checks:** Custom static security scanner
- **GitHub Integration:** GitHub repository and source-file retrieval
- **Testing:** pytest
- **Version Control:** Git and GitHub

## Project Structure

```text
SmartCodeAI/
├── app.py
├── analyzer.py
├── security_scanner.py
├── finding_deduplicator.py
├── github_service.py
├── test_generator.py
├── test_runner.py
├── templates/
│   ├── index.html
│   └── github.html
├── static/
│   └── style.css
├── tests/
│   ├── test_app.py
│   └── test_finding_deduplicator.py
├── requirements.txt
└── README.md
```

The structure above shows the main application files. Additional test files or configuration files may be present in your local project.

## Getting Started

### Prerequisites

- Python 3.11 or later recommended
- pip
- Git (optional, for cloning the repository)

### 1. Clone the repository

Replace the placeholder with your actual GitHub repository URL.

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SmartCodeAI
```

Alternatively, open your existing project folder in VS Code.

### 2. Create a virtual environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the application

```bash
python app.py
```

Open the local address displayed in the terminal, typically:

```text
http://127.0.0.1:5000
```

## Running Automated Tests

Run the project test suite from the root directory:

```bash
python -m pytest -q
```

The test suite covers code-analysis behavior and Flask routes. Run it against your current codebase to verify the latest changes.

## Security Considerations

- Analyze untrusted source code as text whenever possible.
- Static analysis can miss vulnerabilities and may produce false positives.
- Test execution must be isolated before accepting untrusted code.
- Never commit credentials, access tokens, or private configuration files.
- Keep Flask debug mode restricted to local development.
- Use appropriate timeouts, memory limits, and operating-system isolation before deploying execution features.

## Current Limitations

- Static checks do not replace a complete security audit.
- Test generation supports only the patterns implemented in the current generator.
- GitHub review is limited to eligible files and the repository access supported by the application.
- Secure, production-grade execution isolation is not yet implemented.

## Future Improvements

- Add stronger language-aware parsing and analysis.
- Improve security rules and reduce false positives.
- Expand test generation to handle more function patterns and edge cases.
- Add isolated execution using containers or another suitable sandbox.
- Add code-review history, filtering, and exportable reports.
- Introduce continuous integration to run tests automatically on each push.

## Project Status

SmartCode AI is an educational and portfolio project demonstrating Flask development, static analysis, security scanning, GitHub integration, automated test generation, and software testing.


## Screenshots

### Home Dashboard
![SmartCode AI Home Dashboard](screenshots/HomeDashboard.png)

### Code Review Dashboard
![SmartCode AI Code Review](screenshots/CodeReview.png)

### GitHub Repository Review
![SmartCode AI GitHub Review](screenshots/github-repository-review.png)


## Author

**Singarapu Divya**

B.Tech — Computer Science and Engineering

Lendi Institute of Engineering and Technology
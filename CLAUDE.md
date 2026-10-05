# AutoEdu-Agent: Project Guidelines for Claude Code & AI Assistants

AutoEdu-Agent is an open-source autonomous exam and homework solver for online learning platforms (Onluyen.vn).

## Core Architecture
- **Browser Automation**: `autoedu/browser/` using Playwright Chromium persistent context (`~/.onluyen-browser-profile`).
- **MathML & DOM Extraction**: `autoedu/extractor/mathml_parser.py` converting `<math>`, `<mover>`, `<msup>`, etc. into clean math text.
- **AI Solver Engine**: `autoedu/ai/` using Gemini Web cookies or Google AI Studio Free API.
- **Question Types**:
  - Part I: Multiple choice (A, B, C, D)
  - Part II: True / False (4 statements a, b, c, d)
  - Part III: Short answer / Numeric input (standardized decimals with comma `,`)
- **1-Time Free Trial**: `autoedu/trial.py` allowing a single free evaluation run without prior `.env` configuration.

## Essential Commands
- Show status & trial availability: `python cli.py status`
- Test AI connection: `python cli.py test-ai`
- Scan assignments: `python cli.py scan`
- Run 1-time free trial: `python cli.py trial --url "<URL>"`
- Full solve and submit: `python cli.py solve --url "<URL>"`

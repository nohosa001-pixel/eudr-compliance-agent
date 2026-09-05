# Contributing to EUDRAgent

Thank you for your interest in contributing to the **EUDR Compliance & TRACES-NT DDS Platform**!

## Development & Testing

1. Clone the repository:
   ```bash
   git clone https://github.com/nohosa001-pixel/eudr-compliance-agent.git
   cd eudr-compliance-agent
   ```

2. Setup virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. Run test suite:
   ```bash
   pytest tests/
   ```

## Code Guidelines
- Follow PEP 8 style standards.
- Ensure all MCP (Model Context Protocol) tools include deterministic validation and clear JSON schemas.
- Maintain 100% passing test coverage.

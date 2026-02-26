# Contributing to SmarterMail Log Tool

Thank you for considering contributing to the **SmarterMail Log Tool** project! Contributions are welcome and greatly appreciated. Here are some guidelines to help you get started.

---

## How Can You Contribute?
1. **Report Issues**:
   - If you encounter bugs or have suggestions, please [open an issue](https://github.com/T313C0mun1s7/sm-logtool/issues).
   - Provide as much detail as possible, including:
     - Steps to reproduce the issue.
     - Expected vs. actual behavior.
     - Relevant log files, error messages, or screenshots.

2. **Submit Code Changes**:
   - Bug fixes, new features, or performance improvements are welcome.
   - Before starting work on a significant change, please [open an issue](https://github.com/T313C0mun1s7/sm-logtool/issues) or comment on an existing one to discuss your idea.

3. **Improve Documentation**:
   - Help improve the README, add examples, or clarify existing content.

4. **Test and Review**:
   - Test the tool on various SmarterMail logs.
   - Review open pull requests and provide feedback.

---

## Getting Started
1. **Fork the Repository**:
   - Click the "Fork" button at the top of the repository.
   - Clone your fork locally:
     ```bash
     git clone https://github.com/your-username/sm-logtool.git
     cd sm-logtool
     ```

2. **Set Up Your Development Environment**:
   - Ensure you have Python 3.10+ installed.
   - (Recommended) Create and activate a virtual environment:
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```
   - Install the project in editable mode with test and lint dependencies:
     ```bash
     python -m pip install -e ".[test,lint]"
     ```

3. **Create a New Branch**:
   - Use a descriptive branch name for your changes:
     ```bash
     git checkout -b feature/your-feature-name
     ```

4. **Make Your Changes**:
   - Follow the coding standards outlined below.
   - Add or update tests where applicable.

5. **Run Tests**:
   - Before submitting your changes, ensure all tests pass:
     ```bash
     python -m ruff check .
     python -m pytest -q test/test_line_length_policy.py \
       test/test_public_docstrings.py
     pytest -q
     python -m unittest discover test
     ```

6. **Commit and Push**:
   - Commit your changes with a descriptive message:
     ```bash
     git commit -m "Add [your feature or fix]: [short description]"
     ```
   - Push to your fork:
     ```bash
     git push origin feature/your-feature-name
     ```

---

## Coding Standards

- Target Python 3.10+, follow PEP 8, and indent with four spaces.
- Use `snake_case` for modules/functions/variables, `CapWords` for classes,
  and `UPPER_SNAKE_CASE` for constants.
- Keep lines at or below 79 characters unless there is a strong, documented
  reason to exceed that limit.
- Prefer type hints where they add clarity, and use `pathlib.Path` for
  filesystem work.
- Provide concise docstrings for public modules, classes, functions, and
  methods in line with PEP 257.
- Avoid nesting `if` statements deeper than two levels; refactor with guard
  clauses, flattened conditionals, dispatch tables, or polymorphism instead.
- Write modular, focused code: apply the Single Responsibility Principle, keep
  functions short (aim for ≤20 lines), and group related behavior into classes
  instead of relying on globals.
- Embrace Pythonic readability: use comprehensions/generators for sequence
  transforms, context managers for resource handling, and f-strings for
  formatting.
- Choose descriptive, intention-revealing names (for example `total_sales`)
  and avoid ambiguous identifiers such as `l`, `O`, or `I`.
- Handle errors deliberately: catch specific exceptions, log relevant context,
  and use `try`/`except`/`else`/`finally` to manage alternate flows and
  cleanup.
- Test rigorously: add unit tests under `test/test_*.py`, cover edge cases,
  and run both `pytest -q` and `python -m unittest discover test` before
  opening a pull request.
- Optimize when data demands it: choose the right data structures, profile
  before tuning, and reduce expensive I/O or function calls via caching when
  it helps.
- Stay pragmatic: treat these standards as tools for clarity and
  maintainability, and document intentional deviations when they improve the
  overall design.

## Submitting a Pull Request
1. Navigate to your fork on GitHub.
2. Click the **New Pull Request** button.
3. Fill out the pull request template with:
   - A brief description of your changes.
   - Any issues your changes address (e.g., `Closes #123`).
   - Any additional context or screenshots if necessary.
4. Submit your pull request for review.

---

## Code of Conduct
Please respect other contributors and maintain a friendly and inclusive environment. See the [Code of Conduct](CODE_OF_CONDUCT.md) for more details.

---

## Licensing
By contributing to this repository, you agree that your contributions will be licensed under the same license as the project: **GNU Affero General Public License (AGPL-3.0)**.

---

## Need Help?
If you have any questions or need guidance, feel free to [open a discussion](https://github.com/T313C0mun1s7/sm-logtool/discussions).

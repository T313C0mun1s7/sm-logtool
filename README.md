
# sm-logtool

sm-logtool is a TUI (Text User Interface) focused on making searches and sub-searches against **SmarterMail** logs faster and easier. It targets Linux servers that host SmarterMail or have direct access to the SmarterMail log directory.

---

## Features

- Interactive TUI for an intuitive log search experience directly in your terminal.
- Efficiently search across large SmarterMail log files without leaving the server.
- Perform sub-searches to refine results in place.
- Configuration-driven setup for flexible log and output management.
- Designed for native execution on Linux systems where the logs are stored.

---

## Installation

Installation will be provided via a setup script or Python package manager (e.g., `pip` or `pipx`). The goal is to expose a single command in your system `$PATH` for easy access.

1. Install the app (exact method TBD):
   ```bash
   pip install sm-logtool
   ```

2. Verify the installation:
   ```bash
   sm-logtool --version
   ```

3. Ensure the server has access to the SmarterMail log directory described in your configuration.

---

## Usage

### Configuration
Before running the app, configure a file such as `config.yaml` with the following details:
- Absolute path to the SmarterMail logs directory (usually inside `/var` on the same host as SmarterMail).
- Output directory for filtered or exported logs.
- Additional application-specific settings (search presets, theme options, etc.).

### Running the App
1. Launch the TUI from the terminal:
   ```bash
   sm-logtool
   ```

2. Follow the on-screen prompts:
   - Choose the log type you want to inspect.
   - Pick from the available log files (e.g., one per day, named by date).
   - Enter your search term or perform sub-searches to dig deeper.

3. Results appear within the TUI and can optionally be written to the output directory defined in your configuration.

### TUI Basics
- `q` — quit the application
- `/` — open the search action (placeholder for now)
- `r` — refresh the file list

### Example Workflow
- During local development, drop test files into the `sample_logs/` directory included in this repository and run `sm-logtool` to confirm the CLI can discover them.
- SSH into the SmarterMail host (or open a local terminal) when you are ready to work with live data and update `--logs-dir` to point at the real log folder.
- Run `sm-logtool`, explore the logs, and export any snippets that you need for troubleshooting or sharing.

---

## Contributing

Contributions are welcome! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines.

---

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md) to ensure respectful and constructive collaboration.

---

## License

This project is licensed under the GNU Affero General Public License (AGPL-3.0).  
For more details, see the [LICENSE](LICENSE) file or visit [GNU AGPL-3.0 License](https://www.gnu.org/licenses/agpl-3.0.html).

---

## Acknowledgments

- Thanks to the open-source community for their invaluable resources and inspiration.

---

## Design Notes

For a deeper look at search behavior, grouping, fuzzy/regex modes, zipped logs, and UI plans, see:
- `docs/SEARCH_NOTES.md`

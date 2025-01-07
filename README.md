
# sm-logtool

A containerized application with a TUI (Text User Interface) for improved log searches and sub-searches tailored for **SmarterMail** logs. This project focuses on Linux-based environments, providing efficient tools to analyze and filter log data while leveraging containerization for isolation.

---

## Features

- Interactive TUI for an intuitive log search experience.
- Efficiently search through large SmarterMail log files.
- Perform sub-searches to refine results quickly.
- Configuration-driven setup for flexible log and output management.
- Designed for Linux systems with containerized deployment.

---

## Installation

The app will be installable via a setup script or package manager (e.g., `pip` or `pipx`), ensuring the main binary is placed in your system's PATH.

1. Install the app (method to be finalized):
   ```bash
   pip install sm-logtool
   ```

2. Verify the installation:
   ```bash
   logs --version
   ```

3. Ensure the app is ready to run by configuring the container environment (see **Docker Integration** below).

---

## Usage

### Configuration
Before running the app, ensure the configuration file (`config.yaml` or similar) is properly set up. This file will define:
- The path to the logs directory (mounted from the email server).
- The output directory for filtered logs.
- Other application-specific settings.

### Running the App
1. Start the app using the main command:
   ```bash
   logs
   ```

2. Follow the interactive TUI prompts:
   - Select the log type.
   - Choose from available logs (e.g., one per day, named by date).
   - Input your search term or sub-search term.

3. The app will process the logs and provide results or save filtered logs as specified in the configuration file.

---

## Docker Integration

The application is designed to run within a Docker container for isolation and portability. Here’s how Docker fits into the workflow:

1. **Mount Logs**:
   - The container will mount the log directory from the email server:
     ```bash
     docker run -v /path/to/logs:/app/logs sm-logtool
     ```

2. **TUI Interaction**:
   - Access the containerized TUI from the host system or a remote terminal.

3. **Host Independence**:
   - The Docker container can be hosted anywhere (not necessarily on the mail server itself). Ensure the log directory is accessible via a mounted volume or network share.

Future updates will detail the exact Docker command to interact with the TUI.

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

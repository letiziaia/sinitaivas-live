# Runbook

This document explains how to install, configure, and run the Sinitaivas Live data collection service.

## Prerequisites

- Python 3.10+
- Git

## Installation

1. Clone the repository:  
   `git clone https://github.com/letiziaia/sinitaivas-live.git`
2. Change to project directory:  
   `cd sinitaivas-live`
3. (Optional) Create and activate a virtual environment with `pipenv`, and install dependencies
   ```
   pipenv install --dev
   pipenv shell
   ```
   Alternatively, just install _sinitaivas-live_:
   ```
   pip install -e .
   ```

## Running the Collector

- **Directly**:  
  `python -m sinitavas_live.main --mode fresh`
- or _From the installed package_:
  `sinitaivas-live --mode fresh`
- or **as a service** (in Unix, after setting up `sinitaivas-live.service` as explained under `/ops`):

  ```{bash}
  systemctl daemon-reload
  systemctl start sinitaivas-live
  systemctl enable sinitaivas-live
  ```

## Logs & Monitoring

- All logs are shown on stdout.
- Logs with level WARNING and above are also written to a `.log` file in the working directory. To view live output from those, you can use `tail -f <path-to>.log`

## Stopping & Restarting

- If running in foreground, press `Ctrl+C` or `Cmd+C`.
- For the managed service, use:
  ```{bash}
  systemctl stop sinitaivas-live
  systemctl start sinitaivas-live
  ```

## Troubleshooting

- **Cursor resume failures**: delete or move the old cursor file
- **High memory usage**: ensure gzip compression is enabled in `ops/run_service.sh`.

## Further Reading

- See `/ops` for deployment scripts.
- See `CONTRIBUTING.md` for development guidelines.

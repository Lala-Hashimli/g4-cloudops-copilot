# G4 CloudOps Copilot

G4 CloudOps Copilot is a production-style Telegram bot for the Group 4 Azure 3-tier web application environment. It is designed to run on the Ansible/Ops VM in polling mode, watch Azure metrics and application health, run safe SSH checks to private VMs, explain common incidents, and send concise Telegram alerts.

## What the bot does

- Responds to Telegram commands such as `/status`, `/health`, `/nginx`, `/backend`, `/appgw`, `/sql`, `/sonarqube`, `/analyze`, and `/runbook`.
- Monitors:
  - Application Gateway frontend and API route availability
  - VM CPU from Azure Monitor
  - Azure SQL CPU when available
  - Nginx service and error patterns
  - Backend health and logs
  - SonarQube health
  - Optional GitHub Actions status
- Explains incidents with:
  - built-in rule-based detection first
  - Gemini API when configured
- Runs on the Ansible VM using Telegram polling, so no inbound webhook port is required.

## Where it runs

- Local development folder:
  - `C:\Users\lalah\Desktop\g4-cloudops-copilot\tools\cloudops-copilot`
- Production runtime target:
  - `vm-ansible-group4b-1pdu`
- Production service:
  - `systemd/g4-cloudops-copilot.service`

## How it connects

### Azure

The bot uses a Service Principal with these environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

Recommended permissions:

- `Reader`
- `Monitoring Reader`
- `Log Analytics Reader` if Log Analytics queries are later added

### Private VMs

The bot runs on the Ansible VM and uses SSH from there to:

- `10.20.2.4` frontend VM
- `10.20.3.4` backend VM
- `4.193.171.24` SonarQube VM

It only runs predefined safe commands from code and never executes raw Telegram user input over SSH.

### Gemini

If `GEMINI_API_KEY` is configured, the bot sends sanitized incident context to Gemini for a simple explanation and next steps. If Gemini is missing or fails, the rule-based analyzer is still used.

## Folder structure

```text
tools/cloudops-copilot/
├── README.md
├── requirements.txt
├── .env.example
├── rules.yml
├── run_local.sh
├── install_on_vm.sh
├── systemd/
│   └── g4-cloudops-copilot.service
└── src/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── bot.py
    ├── monitor_loop.py
    ├── azure_client.py
    ├── ssh_client.py
    ├── analyzer.py
    ├── gemini_client.py
    ├── message_templates.py
    ├── checks/
    └── utils/
```

## Create `.env`

1. Copy `.env.example` to `.env`
2. Fill in real values
3. Do not commit `.env`

Important values:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- Azure Service Principal values
- `SSH_KEY_PATH`
- `APP_GATEWAY_URL`
- `GEMINI_API_KEY` optional

## Local development

Local development is best for:

- `/start`
- `/help`
- `/analyze`
- message formatting
- Gemini integration

Azure metrics and private VM SSH checks may be unavailable from a laptop.

### Windows note

This project is intended to run on Linux on the Ansible VM. Local development on Windows is still fine for analyzer and Telegram command testing, but SSH and systemd deployment are VM-side tasks.

### Quick local run

From a Linux shell:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

Or:

```bash
./run_local.sh
```

## Deploy to the Ansible VM

1. Copy the project folder to:
   - `/home/azureuser/cloudops-copilot`
2. Create the real `.env`
3. Run manually first:

```bash
cd /home/azureuser/cloudops-copilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

4. If it works, install as a service:

```bash
chmod +x install_on_vm.sh
./install_on_vm.sh
```

## Telegram commands

- `/start`
- `/help`
- `/status`
- `/health`
- `/vms`
- `/appgw`
- `/sql`
- `/nginx`
- `/backend`
- `/sonarqube`
- `/analyze <log text>`
- `/runbook <name>`

## Demo ideas

### Demo 1: Mixed content

Send:

```text
/analyze Mixed Content: The page at https://group4b-demo-appgw.southeastasia.cloudapp.azure.com requested insecure resource http://20.205.212.128/api/ingredients
```

Expected explanation:

- HTTPS page calls HTTP API
- stale frontend build contains wrong API URL
- set `VITE_API_BASE_URL1`
- rebuild and redeploy frontend

### Demo 2: High CPU

On the backend VM:

```bash
yes > /dev/null &
```

The bot should detect high CPU and send an alert.

Stop it:

```bash
pkill yes
```

### Demo 3: Gateway or Nginx issue

Use:

- `/appgw`
- `/nginx`
- `/backend`

to inspect the frontend path, API route, Nginx state, and backend service.

## Security notes

- No secrets are hardcoded.
- `.env.example` only contains placeholders.
- Telegram uses polling, not webhooks.
- Logs mask sensitive values.
- SSH commands are predefined in code.
- The bot is intended to run from the private Ansible/Ops VM.

## Troubleshooting

### Bot starts but Azure checks are skipped

Check:

- Azure Service Principal values in `.env`
- assigned Azure roles

### SSH checks fail

Check:

- `SSH_KEY_PATH`
- private key permissions
- connectivity from Ansible VM to private VM

### Gemini explanations are missing

Check:

- `GEMINI_API_KEY`
- outbound internet access from the Ansible VM

### Frequent duplicate alerts

Tune:

- `CHECK_INTERVAL_SECONDS`
- `ALERT_COOLDOWN_SECONDS`

### Frontend mixed-content issue

If the frontend loads over HTTPS but requests `http://20.205.212.128/api/ingredients`, the fix is:

1. set `VITE_API_BASE_URL1` to `https://group4b-demo-appgw.southeastasia.cloudapp.azure.com`
2. rebuild frontend
3. redeploy dist files
4. hard refresh browser


"""Build EC2 startup scripts for the Weather and Advisor apps."""

import base64
import shlex
from pathlib import Path


def build_user_data(tier, environment):
    """Create a startup script with app files and settings."""

    app_dir = Path(__file__).resolve().parent.parent / tier.app_dir

    app_js = (app_dir / "app.js").read_bytes()
    package_json = (app_dir / "package.json").read_bytes()

    files = {
        "app.js": app_js,
        "package.json": package_json,
    }

    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update",
        "apt-get install -y curl ca-certificates",
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "mkdir -p /opt/app",
    ]

    for name, content in files.items():
        encoded = base64.b64encode(content).decode("ascii")

        lines.append(
            f"echo {shlex.quote(encoded)} | base64 -d > /opt/app/{name}"
        )

    lines.extend([
        "cd /opt/app",
        "npm install --omit=dev --no-audit --no-fund",
    ])

    if tier.name == "weather":
        lines.append(
            "curl -fsSL "
            "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem "
            "-o /opt/app/rds-ca.pem"
        )

    lines.append("touch /opt/app/app.env")

    for key, value in environment.items():
        lines.append(
            f"echo {shlex.quote(key + '=' + str(value))} "
            ">> /opt/app/app.env"
        )

    lines.extend([
        "chmod 600 /opt/app/app.env",
        "cat > /etc/systemd/system/weather-lab.service <<'EOF'",
        "[Unit]",
        "Description=ITMO 544 Weather Lab Application",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        "WorkingDirectory=/opt/app",
        "EnvironmentFile=/opt/app/app.env",
        "ExecStart=/usr/bin/node /opt/app/app.js",
        "Restart=always",
        "RestartSec=5",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "EOF",
        "systemctl daemon-reload",
        "systemctl enable --now weather-lab.service",
    ])

    return "\n".join(lines) + "\n"


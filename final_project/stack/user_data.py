
"""Build Python EC2 startup scripts for the Final Weather Advisor."""

import base64
import gzip
import json
from pathlib import Path


def build_user_data(tier, environment):
    """Build Python cloud-init user data for a Node.js application."""

    app_dir = Path(__file__).resolve().parent.parent / tier.app_dir

    files = {
        "app.js": (app_dir / "app.js").read_bytes(),
        "package.json": (app_dir / "package.json").read_bytes(),
    }

    encoded_files = {
        name: base64.b64encode(
            gzip.compress(content, mtime=0)
        ).decode("ascii")
        for name, content in files.items()
    }

    service_name = f"final-{tier.name}.service"

    payload = {
        "files": encoded_files,
        "environment": {
            key: str(value)
            for key, value in environment.items()
        },
        "service_name": service_name,
        "tier_name": tier.name,
    }

    script = '''#!/usr/bin/env python3

import base64
import gzip
import json
import os
import pathlib
import subprocess
import urllib.request
import shutil

DATA = json.loads(PAYLOAD_PLACEHOLDER)


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():

    os.environ["DEBIAN_FRONTEND"] = "noninteractive"

    import platform
    import tarfile
    import tempfile

    architecture = platform.machine()

    if architecture not in ("x86_64", "aarch64"):
        raise RuntimeError(
            "Unsupported CPU architecture: " + architecture
        )

    node_arch = "x64" if architecture == "x86_64" else "arm64"

    node_version = "v22.16.0"

    filename = f"node-{node_version}-linux-{node_arch}.tar.xz"

    url = (
        f"https://nodejs.org/dist/"
        f"{node_version}/{filename}"
    )

    with tempfile.TemporaryDirectory() as temp_dir:

        archive = pathlib.Path(temp_dir) / filename

        urllib.request.urlretrieve(url, archive)

        with tarfile.open(archive, "r:xz") as tar:
            tar.extractall(temp_dir, filter="data")

        extracted = (
            pathlib.Path(temp_dir)
            / filename.removesuffix(".tar.xz")
        )

        destination = pathlib.Path("/opt/node")

        if destination.exists():
            shutil.rmtree(destination)

        destination.parent.mkdir(parents=True, exist_ok=True)

        # Preserve Node.js and npm symbolic links.
        shutil.copytree(
            extracted,
            destination,
            symlinks=True,
        )

    os.environ["PATH"] = (
        "/opt/node/bin:" + os.environ["PATH"]
    )

    # Verify Node.js and npm.
    run("/opt/node/bin/node", "--version")
    run("/opt/node/bin/npm", "--version")

    app_dir = pathlib.Path("/opt/app")

    app_dir.mkdir(parents=True, exist_ok=True)

    for name, encoded in DATA["files"].items():

        content = gzip.decompress(
            base64.b64decode(encoded)
        )

        (app_dir / name).write_bytes(content)

    # Install application dependencies.
    run(
        "/opt/node/bin/npm",
        "install",
        "--omit=dev",
        "--no-audit",
        "--no-fund",
        cwd=str(app_dir),
    )

    # Create application environment file.
    env_path = app_dir / "app.env"

    env_lines = [
        key + "=" + value
        for key, value in DATA["environment"].items()
    ]

    env_path.write_text(
        "\\n".join(env_lines) + "\\n"
    )

    env_path.chmod(0o600)

    # Create systemd service.
    service = DATA["service_name"]

    unit = (
        "[Unit]\\n"
        "Description=Final Weather Advisor - "
        + DATA["tier_name"] + "\\n"
        "After=network-online.target\\n"
        "Wants=network-online.target\\n"
        "\\n"
        "[Service]\\n"
        "Type=simple\\n"
        "WorkingDirectory=/opt/app\\n"
        "EnvironmentFile=/opt/app/app.env\\n"
        "ExecStart=/opt/node/bin/node /opt/app/app.js\\n"
        "Restart=always\\n"
        "RestartSec=5\\n"
        "\\n"
        "[Install]\\n"
        "WantedBy=multi-user.target\\n"
    )

    pathlib.Path(
        "/etc/systemd/system", service
    ).write_text(unit)

    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "--now", service)


if __name__ == "__main__":
    main()

'''

    return script.replace(
        "PAYLOAD_PLACEHOLDER",
        repr(json.dumps(payload)),
    )

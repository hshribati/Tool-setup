#!/bin/bash
set -e

export DEBIAN_FRONTEND=noninteractive

# Install Node.js and npm
apt-get update -y
apt-get install -y nodejs npm

# Create application folder
mkdir -p /opt/viewer-app
cd /opt/viewer-app

# Create package.json
cat > package.json <<'PACKAGE'
{
  "name": "viewer-app",
  "version": "1.0.0",
  "main": "app.js",
  "dependencies": {
    "express": "^4.19.2",
    "@aws-sdk/client-s3": "^3.600.0"
  }
}
PACKAGE

cat > /opt/viewer-app/app.js <<'APP_CODE'
const express = require('express');
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');

const app = express();
const s3 = new S3Client({ region: process.env.AWS_REGION });
const BUCKET = process.env.BUCKET_NAME;
const PORT = process.env.PORT || 3000;

async function getFileContent() {
  const response = await s3.send(new GetObjectCommand({
    Bucket: BUCKET,
    Key: 'shared.txt'
  }));

  return await response.Body.transformToString();
}

app.get('/', async (req, res) => {
  try {
    const content = await getFileContent();

    res.set('Cache-Control', 'no-store');
    res.type('html').send(`
      <h1>Viewer</h1>
      <h2>Content of shared.txt</h2>
      <pre id="content"></pre>
      <button onclick="location.reload()">Refresh</button>
      <script>
        document.getElementById('content').textContent =
          ${JSON.stringify(content)};
      </script>
    `);
  } catch (err) {
    res.status(500).send(
      '<h1>Viewer</h1><p>Unable to load shared.txt: ' +
      String(err.message).replace(/&/g, '&amp;').replace(/</g, '&lt;') +
      '</p><button onclick="location.reload()">Refresh</button>'
    );
  }
});

app.listen(PORT, () => console.log(`Viewer listening on ${PORT}`));

APP_CODE

# Install application packages
cd /opt/viewer-app
npm install --omit=dev

# Create automatic startup service
cat > /etc/systemd/system/viewer.service <<'SERVICE'
[Unit]
Description=Lab03 Viewer Application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/viewer-app
Environment=AWS_REGION=us-east-2
Environment=BUCKET_NAME=cloud-lab03-files-100995727963
Environment=PORT=3000
ExecStart=/usr/bin/node /opt/viewer-app/app.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# Start the Viewer automatically
systemctl daemon-reload
systemctl enable viewer.service
systemctl start viewer.service

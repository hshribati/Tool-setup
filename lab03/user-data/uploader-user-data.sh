#!/bin/bash
set -e

export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y nodejs npm

mkdir -p /opt/uploader-app
cd /opt/uploader-app

cat > package.json <<'EOF'
{
  "name": "uploader-app",
  "version": "1.0.0",
  "main": "app.js",
  "dependencies": {
    "express": "^4.19.2",
    "multer": "^1.4.5-lts.1",
    "@aws-sdk/client-s3": "^3.600.0"
  }
}
EOF

cat > /opt/uploader-app/app.js <<'APP_CODE'
const express = require('express');
const multer = require('multer');
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');

const app = express();
const MAX_FILE_SIZE = 1 * 1024 * 1024;

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: MAX_FILE_SIZE },
  fileFilter: (req, file, cb) => {
    const isTxt = file.mimetype === 'text/plain' &&
      file.originalname.toLowerCase().endsWith('.txt');

    if (!isTxt) {
      return cb(new Error('ONLY_TXT_ALLOWED'));
    }
    cb(null, true);
  },
});

const s3 = new S3Client({ region: process.env.AWS_REGION });
const BUCKET = process.env.BUCKET_NAME;
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send(`
    <h1>Uploader</h1>
    <form method="POST" action="/upload" enctype="multipart/form-data">
      <input type="file" name="txtfile" accept=".txt" required>
      <p>Only .txt files, max 1MB</p>
      <button type="submit">Upload</button>
    </form>
  `);
});

app.post('/upload', (req, res) => {
  upload.single('txtfile')(req, res, async (err) => {
    if (err) {
      if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(413).send(
          '<p>Upload failed: file exceeds the 1MB limit.</p><a href="/">Try again</a>'
        );
      }

      if (err.message === 'ONLY_TXT_ALLOWED') {
        return res.status(415).send(
          '<p>Upload failed: only .txt files are allowed.</p><a href="/">Try again</a>'
        );
      }

      return res.status(400).send(
        '<p>Upload failed: ' + err.message + '</p><a href="/">Try again</a>'
      );
    }

    if (!req.file) {
      return res.status(400).send('No file selected.');
    }

    try {
      await s3.send(new PutObjectCommand({
        Bucket: BUCKET,
        Key: 'shared.txt',
        Body: req.file.buffer,
        ContentType: 'text/plain',
      }));

      res.send('<p>Upload successful.</p><a href="/">Upload another</a>');
    } catch (err2) {
      res.status(500).send('Upload failed: ' + err2.message);
    }
  });
});

app.listen(PORT, () => console.log(`Uploader listening on ${PORT}`));

APP_CODE

# Install application packages
cd /opt/uploader-app
npm install --omit=dev

# Create automatic startup service
cat > /etc/systemd/system/uploader.service <<'SERVICE'
[Unit]
Description=Lab03 Uploader Application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/uploader-app
Environment=AWS_REGION=us-east-2
Environment=BUCKET_NAME=cloud-lab03-files-100995727963
Environment=PORT=3000
ExecStart=/usr/bin/node /opt/uploader-app/app.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# Start the Uploader automatically
systemctl daemon-reload
systemctl enable uploader.service
systemctl start uploader.service

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

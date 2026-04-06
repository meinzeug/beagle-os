// Beagle OS Gaming Kiosk - MIT Licensed
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const rootDir = path.join(__dirname, '..');
const packageJson = JSON.parse(fs.readFileSync(path.join(rootDir, 'package.json'), 'utf8'));
const outputDir = path.join(rootDir, 'dist');
const artifactArg = process.argv[2] || '';
const downloadUrlArg = process.argv[3] || process.env.BEAGLE_KIOSK_RELEASE_DOWNLOAD_URL || '';

function locateArtifact() {
  if (artifactArg) {
    return path.resolve(process.cwd(), artifactArg);
  }

  const entries = fs
    .readdirSync(outputDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && /^beagle-kiosk-v.+-linux-x64\.AppImage$/.test(entry.name))
    .map((entry) => path.join(outputDir, entry.name))
    .sort();

  if (entries.length !== 1) {
    throw new Error(
      `Unable to auto-detect kiosk artifact in ${outputDir}. Pass the AppImage path explicitly.`
    );
  }

  return entries[0];
}

function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

const artifactPath = locateArtifact();
const assetName = path.basename(artifactPath);
const sha256 = sha256File(artifactPath);
const manifest = {
  version: packageJson.version,
  asset_name: assetName,
  download_url: downloadUrlArg,
  sha256,
  size: fs.statSync(artifactPath).size,
  generated_at: new Date().toISOString(),
};

fs.writeFileSync(
  path.join(outputDir, 'kiosk-release.json'),
  `${JSON.stringify(manifest, null, 2)}\n`,
  'utf8'
);
fs.writeFileSync(
  path.join(outputDir, 'kiosk-release-hash.txt'),
  `${sha256}  ${assetName}\n`,
  'utf8'
);

process.stdout.write(`${path.join(outputDir, 'kiosk-release.json')}\n`);
process.stdout.write(`${path.join(outputDir, 'kiosk-release-hash.txt')}\n`);

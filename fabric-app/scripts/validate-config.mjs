import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parse } from 'yaml';
import { loadEnv } from 'vite';

const config = parse(readFileSync('rayfin/rayfin.yml', 'utf8'));
assert.equal(config.services.auth.enabled, true, 'Fabric auth must be enabled');
assert.equal(config.services.auth.fabric.enabled, true, 'Fabric SSO must be enabled');
assert.equal(config.services.auth.password.enabled, false, 'No deployed password authentication');
assert.equal(config.services.staticHosting.assetAccess, 'protected', 'Protect hosted assets');
assert.equal(config.connectors.length, 1);
assert.equal(config.connectors[0].auth.type, 'delegated');
assert.deepEqual(config.connectors[0].operations, [{ name: 'read' }]);
assert.equal(config.connectors[0].name, 'gold');
const env = { ...loadEnv('production', process.cwd(), ''), ...process.env };
if (process.argv.includes('--live')) {
  assert.equal(env.VITE_DATA_MODE, 'live', 'Deployment must build live mode explicitly');
  for (const key of ['GOLD_WORKSPACE_ID', 'GOLD_WAREHOUSE_ID', 'VITE_FABRIC_WORKSPACE_ID']) {
    assert.match(env[key] ?? '', /^[a-f\d]{8}(-[a-f\d]{4}){3}-[a-f\d]{12}$/i, key + ' is required');
  }
  if (env.VITE_FABRIC_ITEM_ID) assert.match(env.VITE_FABRIC_ITEM_ID, /^[a-f\d-]{36}$/i);
  if (env.VITE_RAYFIN_API_URL) {
    const url = new URL(env.VITE_RAYFIN_API_URL);
    assert(
      url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash,
      'Trusted HTTPS backend required',
    );
  }
}
console.log(
  'PASS: local configuration posture. Cloud permissions, SQL schema discovery and deployment have not been validated.',
);

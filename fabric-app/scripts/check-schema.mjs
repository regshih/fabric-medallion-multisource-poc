import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import {
  SchemaAnalyzer,
  ConfigGenerator,
  ConnectorSchemaAnalyzer,
  ConnectorConfigGenerator,
} from '@microsoft/rayfin-core/analysis';
import { schema } from '../rayfin/.temp/compiled/data/schema.js';
import {
  CustomerProfile,
  CustomerTransaction,
  CustomerSession,
  CustomerAlert,
  QualityCheck,
} from '../rayfin/.temp/compiled/connectors/gold/schema.js';

const workflow = new ConfigGenerator('mssql').generateConfig(
  new SchemaAnalyzer(schema, 'mssql', { log() {} }).analyzeEntities(),
);
const connector = new ConnectorConfigGenerator('fabric-warehouse').generateConfig(
  new ConnectorSchemaAnalyzer(
    [CustomerProfile, CustomerTransaction, CustomerSession, CustomerAlert, QualityCheck],
    'fabric-warehouse',
    { log() {} },
  ).analyzeEntities(),
);
const event = Object.values(workflow.entities)[0];
assert.equal(event.permissions.length, 1);
assert.equal(event.permissions[0].role, 'authenticated');
assert.deepEqual(event.permissions[0].actions.map((a) => a.action).sort(), ['create', 'read']);
assert(
  event.permissions[0].actions.every((a) => a.policy.database === '@claims.sub eq @item.user_id'),
);
assert.equal(Object.keys(connector.entities).length, 5);
for (const entity of Object.values(connector.entities)) {
  assert.deepEqual(entity.permissions, [{ role: 'authenticated', actions: ['read'] }]);
  assert.equal((entity.keyFields ?? []).length, 0);
}
mkdirSync('.local', { recursive: true });
writeFileSync('.local/workflow-dab.json', JSON.stringify(workflow, null, 2));
writeFileSync('.local/gold-connector-dab.json', JSON.stringify(connector, null, 2));
console.log(
  'PASS: compiled Rayfin schema, creator policies, append-only events and five keyless read-only connector entities. No cloud calls.',
);

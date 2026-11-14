import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parse } from 'yaml';
import {
  SchemaAnalyzer,
  ConfigGenerator,
  ConnectorSchemaAnalyzer,
  ConnectorConfigGenerator,
} from '@microsoft/rayfin-core/analysis';
import { schema } from '../rayfin/data/schema';
import {
  CustomerProfile,
  CustomerTransaction,
  CustomerSession,
  CustomerAlert,
  QualityCheck,
} from '../rayfin/connectors/gold/schema';

describe('generated authorization configuration', () => {
  it('generates only owner-scoped create/read for investigation events', () => {
    const entities = new SchemaAnalyzer(schema, 'mssql', { log: () => {} }).analyzeEntities();
    const generated = new ConfigGenerator('mssql').generateConfig(entities);
    const entity = Object.values(generated.entities)[0];
    expect(entity.permissions).toHaveLength(1);
    expect(entity.permissions[0].role).toBe('authenticated');
    const actions = entity.permissions[0].actions;
    expect(actions.map((a) => (typeof a === 'string' ? a : a.action)).sort()).toEqual([
      'create',
      'read',
    ]);
    for (const action of actions) {
      expect(typeof action).toBe('object');
      if (typeof action === 'object')
        expect(action.policy).toEqual({ database: '@claims.sub eq @item.user_id' });
    }
    expect(entity['x-schema']?.fields.note).toBeDefined();
  });
  it('generates five read-only keyless connector entities mapped to the app schema', () => {
    const entities = new ConnectorSchemaAnalyzer(
      [CustomerProfile, CustomerTransaction, CustomerSession, CustomerAlert, QualityCheck],
      'fabric-warehouse',
      { log: () => {} },
    ).analyzeEntities();
    const generated = new ConnectorConfigGenerator('fabric-warehouse').generateConfig(entities);
    expect(Object.keys(generated.entities)).toHaveLength(5);
    for (const entity of Object.values(generated.entities)) {
      expect(JSON.stringify(entity.source)).toContain('risk_app');
      expect(entity.keyFields ?? []).toHaveLength(0);
      expect(entity.permissions).toEqual([{ role: 'authenticated', actions: ['read'] }]);
    }
  });
  it('requires delegated source auth and never enables a Gold mutation', () => {
    const config = parse(readFileSync('rayfin/rayfin.yml', 'utf8'));
    expect(config.services.auth.enabled).toBe(true);
    expect(config.services.auth.fabric.enabled).toBe(true);
    expect(config.services.auth.password.enabled).toBe(false);
    expect(config.connectors[0].auth.type).toBe('delegated');
    expect(config.connectors[0].operations).toEqual([{ name: 'read' }]);
    const sql = readFileSync('sql/01_app_serving_views.sql', 'utf8');
    expect(sql.match(/JOIN dbo\.Fact/g)).toHaveLength(3);
    expect(sql.match(/FROM dbo\.AggCustomerRiskProfile p/g)).toHaveLength(3);
    expect(sql).not.toMatch(/\b(DELETE|TRUNCATE|DROP TABLE|INSERT INTO|UPDATE dbo)\b/i);
  });
});

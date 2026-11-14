import { describe, expect, it } from 'vitest';
import { buildDemo, DEMO_IDENTITY, demoDetail } from '../src/demo';
import {
  eventSchema,
  freshness,
  makeEvent,
  profileSchema,
  reduceCases,
  riskFactors,
} from '../src/domain';

describe('Gold contract and business semantics', () => {
  it('generates deterministic schema-valid customers covering every risk band', () => {
    const data = buildDemo();
    expect(data.profiles).toEqual(buildDemo().profiles);
    expect(new Set(data.profiles.map((p) => p.CustomerID)).size).toBe(120);
    expect(new Set(data.profiles.map((p) => p.CustomerRiskBand)).size).toBe(3);
    expect(profileSchema.array().safeParse(data.profiles).success).toBe(true);
  });
  it('explains every score using the existing Gold formula', () => {
    for (const p of buildDemo().profiles) {
      const computed = Math.min(
        100,
        riskFactors(p).reduce((sum, f) => sum + f.value, 0),
      );
      expect(computed).toBeCloseTo(p.CustomerRiskScore, 1);
      expect(p.CustomerRiskBand).toBe(
        p.CustomerRiskScore >= 80 ? 'High' : p.CustomerRiskScore >= 45 ? 'Medium' : 'Low',
      );
    }
  });
  it('keeps transaction currencies instead of presenting a combined USD total', () => {
    const details = demoDetail(buildDemo().profiles[0]);
    expect(new Set(details.transactions.map((t) => t.Currency))).toEqual(new Set(['USD', 'EUR']));
    expect(
      details.transactions.every((t) => t.CustomerID === buildDemo().profiles[0].CustomerID),
    ).toBe(true);
  });
  it('rejects invalid source scores and never accepts an infinite number', () => {
    const p = buildDemo().profiles[0];
    expect(profileSchema.safeParse({ ...p, CustomerRiskScore: 101 }).success).toBe(false);
    expect(profileSchema.safeParse({ ...p, FraudAlertCount: Infinity }).success).toBe(false);
  });
  it('reports invalid and future freshness as unknown', () => {
    const now = Date.parse('2026-11-13T12:00:00Z');
    expect(freshness('2026-11-13T11:00:00', now)).toBe('Within 24h');
    expect(freshness('2026-09-01T11:00:00Z', now)).toBe('Older than 24h');
    expect(freshness('invalid', now)).toBe('Unknown');
    expect(freshness('2027-01-01T00:00:00Z', now)).toBe('Unknown');
  });
});

describe('investigation event stream', () => {
  it('reconstructs state without losing note-only events', () => {
    const p = buildDemo().profiles[0];
    const first = { ...makeEvent(DEMO_IDENTITY, p), createdAt: '2026-11-13T10:00:00Z' };
    const current = reduceCases([first])[0];
    const update = {
      ...makeEvent(DEMO_IDENTITY, p, current, {
        status: 'Escalated',
        assignee: 'Fraud operations',
        note: 'Review device history.',
      }),
      createdAt: '2026-11-13T10:01:00Z',
    };
    const note = {
      ...makeEvent(DEMO_IDENTITY, p, current, { note: 'Evidence retained.' }, true),
      createdAt: '2026-11-13T10:02:00Z',
    };
    const rebuilt = reduceCases([note, first, update])[0];
    expect(rebuilt.status).toBe('Escalated');
    expect(rebuilt.assignee).toBe('Fraud operations');
    expect(rebuilt.events).toHaveLength(3);
    expect(rebuilt.events[2].note).toBe('Evidence retained.');
  });
  it('rejects invalid status, oversized notes, and blank assignment labels', () => {
    const event = makeEvent(DEMO_IDENTITY, buildDemo().profiles[0]);
    expect(eventSchema.safeParse({ ...event, status: 'Approved for loan' }).success).toBe(false);
    expect(eventSchema.safeParse({ ...event, note: 'x'.repeat(2001) }).success).toBe(false);
    expect(eventSchema.safeParse({ ...event, assignee: ' ' }).success).toBe(false);
  });
  it('ignores orphan events and events for the wrong customer', () => {
    const [a, b] = buildDemo().profiles;
    const created = makeEvent(DEMO_IDENTITY, a);
    const wrong = {
      ...created,
      id: crypto.randomUUID(),
      eventType: 'updated' as const,
      CustomerID: b.CustomerID,
      status: 'Resolved' as const,
    };
    expect(reduceCases([wrong])).toEqual([]);
    expect(reduceCases([created, wrong])[0].status).toBe('Open');
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildDemo, DEMO_IDENTITY, demoDetail } from '../src/demo';
import { makeEvent } from '../src/domain';

const mocks = vi.hoisted(() => {
  const profile = vi.fn();
  const quality = vi.fn();
  const transactions = vi.fn();
  const sessions = vi.fn();
  const alerts = vi.fn();
  const create = vi.fn();
  const paginated = vi.fn();
  const filters: unknown[] = [];
  const limits: number[] = [];
  function builder(execute: typeof profile) {
    const query = {
      select: () => query,
      where: (value: unknown) => {
        filters.push(value);
        return query;
      },
      orderBy: () => query,
      first: (n: number) => {
        limits.push(n);
        return query;
      },
      after: () => query,
      execute,
      executePaginated: paginated,
    };
    return query;
  }
  return {
    profile, quality, transactions, sessions, alerts,
    create, paginated, filters, limits, builder,
  };
});
vi.mock('@microsoft/rayfin-client', () => ({
  ConnectorsRayfinClient: class {
    auth = {
      getSession: () => ({
        isAuthenticated: true,
        user: { id: 'demo-investigator', email: 'investigator@example.test' },
      }),
      signOut: vi.fn(),
    };
    connectors = {
      gold: {
        CustomerProfile: mocks.builder(mocks.profile),
        QualityCheck: mocks.builder(mocks.quality),
        CustomerTransaction: mocks.builder(mocks.transactions),
        CustomerSession: mocks.builder(mocks.sessions),
        CustomerAlert: mocks.builder(mocks.alerts),
      },
    };
    data = { InvestigationEvent: { ...mocks.builder(vi.fn()), create: mocks.create } };
  },
}));
vi.mock('@microsoft/rayfin-auth-provider-fabric', () => ({
  initEmbeddedAuth: vi.fn(),
  ensureSignedInWithFabric: vi.fn(),
}));
import { LiveRepository } from '../src/live';

beforeEach(() => {
  vi.stubEnv('VITE_RAYFIN_API_URL', 'https://approved-app.example.test');
  vi.stubEnv('VITE_RAYFIN_PUBLISHABLE_KEY', 'pk-example');
  vi.stubEnv('VITE_FABRIC_WORKSPACE_ID', '00000000-0000-4000-8000-000000000001');
  vi.stubEnv('VITE_FABRIC_ITEM_ID', '00000000-0000-4000-8000-000000000002');
  vi.stubEnv('VITE_COHORT_LIMIT', '10');
  mocks.filters.length = 0;
  mocks.limits.length = 0;
  mocks.profile.mockResolvedValue(buildDemo().profiles.slice(0, 11));
  mocks.quality.mockResolvedValue([]);
  mocks.transactions.mockResolvedValue([]);
  mocks.sessions.mockResolvedValue([]);
  mocks.alerts.mockResolvedValue([]);
});
describe('configurable live connector', () => {
  it('rejects insecure endpoint configuration before authentication', () => {
    vi.stubEnv('VITE_RAYFIN_API_URL', 'http://untrusted.example.test');
    expect(() => new LiveRepository()).toThrow('HTTPS');
  });
  it('caps the loaded cohort and reports unavailable quality without inventing evidence', async () => {
    mocks.quality.mockRejectedValue(new Error('Permission denied'));
    const snapshot = await new LiveRepository().snapshot();
    expect(snapshot.profiles).toHaveLength(10);
    expect(snapshot.capped).toBe(true);
    expect(snapshot.quality).toEqual([]);
    expect(snapshot.qualityError).toContain('unavailable');
    expect(mocks.limits).toContain(11);
  });
  it('propagates a source failure without returning demo data', async () => {
    mocks.profile.mockRejectedValue(new Error('Source offline'));
    await expect(new LiveRepository().snapshot()).rejects.toThrow('Source offline');
  });
  it('reopens an exact customer outside the bounded cohort using a typed source filter', async () => {
    const profile = buildDemo().profiles[0];
    mocks.profile.mockResolvedValue([profile]);
    expect(await new LiveRepository().profile(profile.CustomerID)).toEqual(profile);
    expect(mocks.filters).toContainEqual({ CustomerID: { eq: profile.CustomerID } });
  });
  it('rejects forged ownership before sending a workflow mutation', async () => {
    const value = makeEvent(
      { id: 'somebody-else', email: 'other@example.test' },
      buildDemo().profiles[0],
    );
    await expect(new LiveRepository().append(value)).rejects.toThrow('identity mismatch');
    expect(mocks.create).not.toHaveBeenCalled();
  });
  it('normalizes serialized dates and follows workflow cursors', async () => {
    const event = makeEvent(DEMO_IDENTITY, buildDemo().profiles[0]);
    mocks.paginated
      .mockResolvedValueOnce({
        items: [{ ...event, createdAt: new Date(event.createdAt) }],
        hasNextPage: true,
        endCursor: 'page-two',
      })
      .mockResolvedValueOnce({ items: [], hasNextPage: false });
    expect(await new LiveRepository().events()).toEqual([event]);
    expect(mocks.paginated).toHaveBeenCalledTimes(2);
  });
  it.each(['string', 'Date'] as const)(
    'accepts connector detail and quality dates as %s values',
    async (representation) => {
      const profile = buildDemo().profiles[0];
      const detail = demoDetail(profile);
      const date = (value: string) => (representation === 'Date' ? new Date(value) : value);
      const expectedDate = (value: string) =>
        representation === 'Date' ? new Date(value).toISOString() : value;
      mocks.transactions.mockResolvedValue(
        detail.transactions.map((row) => ({
          ...row, TransactionTimestamp: date(row.TransactionTimestamp),
        })),
      );
      mocks.sessions.mockResolvedValue(
        detail.sessions.map((row) => ({ ...row, LoginTimestamp: date(row.LoginTimestamp) })),
      );
      mocks.alerts.mockResolvedValue(
        detail.alerts.map((row) => ({ ...row, CreatedTimestamp: date(row.CreatedTimestamp) })),
      );
      const check = {
        source: 'databricks',
        object: 'transactions',
        status: 'PASS',
        quarantine_count: 0,
        pipeline_run_id: profile.pipeline_run_id,
        run_date: '2026-09-01T00:00:00.000Z',
      };
      mocks.quality.mockResolvedValue([{ ...check, run_date: date(check.run_date) }]);
      const repository = new LiveRepository();
      const actual = await repository.detail(profile);
      expect(actual).toEqual({
        transactions: detail.transactions.map((row) => ({
          ...row,
          TransactionTimestamp: expectedDate(row.TransactionTimestamp),
        })),
        sessions: detail.sessions.map((row) => ({
          ...row,
          LoginTimestamp: expectedDate(row.LoginTimestamp),
        })),
        alerts: detail.alerts.map((row) => ({
          ...row,
          CreatedTimestamp: expectedDate(row.CreatedTimestamp),
        })),
        capped: false,
      });
      const snapshot = await repository.snapshot();
      expect(snapshot.quality).toEqual([check]);
      expect(snapshot.qualityError).toBeUndefined();
    },
  );
  it('rejects invalid connector Date objects without inventing dates', async () => {
    const profile = buildDemo().profiles[0];
    mocks.transactions.mockResolvedValue([
      { ...demoDetail(profile).transactions[0], TransactionTimestamp: new Date(NaN) },
    ]);
    await expect(new LiveRepository().detail(profile)).rejects.toThrow();
  });
});

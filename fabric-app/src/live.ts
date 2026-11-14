import { ConnectorsRayfinClient } from '@microsoft/rayfin-client';
import { ensureSignedInWithFabric, initEmbeddedAuth } from '@microsoft/rayfin-auth-provider-fabric';
import { z } from 'zod';
import type { WorkflowSchema } from '../rayfin/data/schema';
import { connectorConfig, type GoldSchema } from '../rayfin/connectors/gold/schema';
import {
  eventSchema,
  profileSchema,
  type Profile,
  type CaseEvent,
  type Identity,
  type Detail,
  type Snapshot,
} from './domain';
import type { Repository } from './repository';

function required(name: string): string {
  const value = import.meta.env[name] as string | undefined;
  if (!value?.trim())
    throw new Error(
      `Live mode requires ${name}. Set the approved deployment configuration and rebuild.`,
    );
  return value.trim();
}
const number = z.coerce.number().finite();
// Rayfin can deserialize date-looking connector values to Date even when the
// SQL projection is VARCHAR. Keep the repository's serialized date contract.
const serializedDate = z.preprocess(
  (value) =>
    value instanceof Date && Number.isFinite(value.getTime()) ? value.toISOString() : value,
  z.string(),
);
const transactionSchema = z.object({
  CustomerID: z.string(),
  TransactionID: z.string(),
  TransactionTimestamp: serializedDate,
  Amount: number,
  Currency: z.string(),
  Channel: z.string(),
  RiskScore: number.nullable(),
  TransactionStatus: z.string(),
});
const sessionSchema = z.object({
  CustomerID: z.string(),
  SessionID: z.string(),
  LoginTimestamp: serializedDate,
  AuthenticationMethod: z.string(),
  MfaUsed: z.boolean(),
  FailedAttempts: number,
  Country: z.string(),
});
const alertSchema = z.object({
  CustomerID: z.string(),
  AlertID: z.string(),
  CreatedTimestamp: serializedDate,
  Severity: z.string(),
  Status: z.string(),
  alertType: z.string(),
  TransactionID: z.string().nullable(),
});
const qualitySchema = z.object({
  source: z.string(),
  object: z.string(),
  status: z.string(),
  quarantine_count: number,
  pipeline_run_id: z.string(),
  run_date: serializedDate,
});

export class LiveRepository implements Repository {
  readonly mode = 'live';
  private readonly client: ConnectorsRayfinClient<
    WorkflowSchema,
    Record<string, never>,
    { gold: GoldSchema }
  >;
  private readonly fabricOptions;
  private readonly limit;
  constructor() {
    const baseUrl = required('VITE_RAYFIN_API_URL');
    const url = new URL(baseUrl);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash)
      throw new Error(
        'Live Rayfin backend must be a trusted absolute HTTPS URL without credentials, query or fragment.',
      );
    this.limit = Number(import.meta.env.VITE_COHORT_LIMIT ?? 200);
    if (!Number.isInteger(this.limit) || this.limit < 1 || this.limit > 1000)
      throw new Error('VITE_COHORT_LIMIT must be an integer from 1 to 1000.');
    this.client = new ConnectorsRayfinClient<
      WorkflowSchema,
      Record<string, never>,
      { gold: GoldSchema }
    >({
      baseUrl,
      publishableKey: required('VITE_RAYFIN_PUBLISHABLE_KEY'),
      authStorage: false,
      connectors: { gold: connectorConfig },
    });
    this.fabricOptions = {
      workspaceId: required('VITE_FABRIC_WORKSPACE_ID'),
      projectId: required('VITE_FABRIC_ITEM_ID'),
      fabricPortalUrl: import.meta.env.VITE_FABRIC_PORTAL_URL ?? 'https://app.fabric.microsoft.com',
      returnOrigin: window.location.origin,
    };
    if (this.fabricOptions.fabricPortalUrl !== 'https://app.fabric.microsoft.com')
      throw new Error('This POC supports the public Fabric portal origin only.');
  }
  async initialize() {
    await initEmbeddedAuth(this.client.auth, this.fabricOptions);
    return this;
  }
  identity(): Identity | null {
    const session = this.client.auth.getSession();
    return session.isAuthenticated && session.user
      ? { id: session.user.id, email: session.user.email ?? 'Fabric investigator' }
      : null;
  }
  async signIn() {
    const session = await ensureSignedInWithFabric(this.client.auth, this.fabricOptions);
    if (!session.isAuthenticated) throw new Error('Fabric sign-in did not complete.');
  }
  async signOut() {
    await this.client.auth.signOut();
  }
  private guard() {
    if (!this.identity()) throw new Error('Your Fabric session has expired. Sign in again.');
  }
  async snapshot(): Promise<Snapshot> {
    this.guard();
    const rows = await this.client.connectors.gold.CustomerProfile.select([
      'CustomerID',
      'TransactionCount30D',
      'TotalTransactionAmount30D',
      'AverageTransactionRiskScore',
      'HighRiskTransactionCount',
      'FailedLoginCount',
      'DistinctDeviceCount',
      'UntrustedDeviceCount',
      'GeographicAnomalyCount',
      'FraudAlertCount',
      'CustomerRiskScore',
      'CustomerRiskBand',
      'gold_loaded_at',
      'pipeline_run_id',
    ])
      .orderBy({ CustomerRiskScore: 'desc', CustomerID: 'asc' })
      .first(this.limit + 1)
      .execute();
    let quality: Snapshot['quality'] = [];
    let qualityError: string | undefined;
    try {
      const checks = await this.client.connectors.gold.QualityCheck.select([
        'source',
        'object',
        'status',
        'quarantine_count',
        'pipeline_run_id',
        'run_date',
      ])
        .first(100)
        .execute();
      quality = qualitySchema.array().parse(checks);
    } catch {
      qualityError = 'Reconciliation query unavailable; no quality assurance is claimed.';
    }
    return {
      profiles: profileSchema.array().parse(rows.slice(0, this.limit)),
      quality,
      fetchedAt: new Date().toISOString(),
      capped: rows.length > this.limit,
      qualityError,
    };
  }
  async profile(customerId: string): Promise<Profile | null> {
    this.guard();
    if (!/^CUST-\d{6}$/.test(customerId)) throw new Error('Invalid customer identifier.');
    const row = await this.client.connectors.gold.CustomerProfile.select([
      'CustomerID',
      'TransactionCount30D',
      'TotalTransactionAmount30D',
      'AverageTransactionRiskScore',
      'HighRiskTransactionCount',
      'FailedLoginCount',
      'DistinctDeviceCount',
      'UntrustedDeviceCount',
      'GeographicAnomalyCount',
      'FraudAlertCount',
      'CustomerRiskScore',
      'CustomerRiskBand',
      'gold_loaded_at',
      'pipeline_run_id',
    ])
      .where({ CustomerID: { eq: customerId } })
      .first(1)
      .execute();
    return row.length ? profileSchema.parse(row[0]) : null;
  }
  async detail(profile: Profile): Promise<Detail> {
    this.guard();
    const where = { CustomerID: { eq: profile.CustomerID } };
    const [transactions, sessions, alerts] = await Promise.all([
      this.client.connectors.gold.CustomerTransaction.select([
        'CustomerID',
        'TransactionID',
        'TransactionTimestamp',
        'Amount',
        'Currency',
        'Channel',
        'RiskScore',
        'TransactionStatus',
      ])
        .where(where)
        .orderBy({ TransactionTimestamp: 'desc', TransactionID: 'asc' })
        .first(51)
        .execute(),
      this.client.connectors.gold.CustomerSession.select([
        'CustomerID',
        'SessionID',
        'LoginTimestamp',
        'AuthenticationMethod',
        'MfaUsed',
        'FailedAttempts',
        'Country',
      ])
        .where(where)
        .orderBy({ LoginTimestamp: 'desc', SessionID: 'asc' })
        .first(51)
        .execute(),
      this.client.connectors.gold.CustomerAlert.select([
        'CustomerID',
        'AlertID',
        'CreatedTimestamp',
        'Severity',
        'Status',
        'alertType',
        'TransactionID',
      ])
        .where(where)
        .orderBy({ CreatedTimestamp: 'desc', AlertID: 'asc' })
        .first(51)
        .execute(),
    ]);
    return {
      transactions: transactionSchema.array().parse(transactions.slice(0, 50)),
      sessions: sessionSchema.array().parse(sessions.slice(0, 50)),
      alerts: alertSchema.array().parse(alerts.slice(0, 50)),
      capped: Math.max(transactions.length, sessions.length, alerts.length) > 50,
    };
  }
  async events(): Promise<CaseEvent[]> {
    this.guard();
    const entries: CaseEvent[] = [];
    let cursor: string | undefined;
    // Bound resource use without silently treating a partial event log as complete.
    for (let page = 0; page < 20; page++) {
      let query = this.client.data.InvestigationEvent.select([
        'id',
        'caseId',
        'CustomerID',
        'user_id',
        'eventType',
        'status',
        'assignee',
        'note',
        'createdAt',
      ])
        .orderBy({ createdAt: 'asc', id: 'asc' })
        .first(500);
      if (cursor) query = query.after(cursor);
      const result = await query.executePaginated();
      entries.push(
        ...result.items.map((row) =>
          eventSchema.parse({
            ...row,
            createdAt: row.createdAt instanceof Date ? row.createdAt.toISOString() : row.createdAt,
          }),
        ),
      );
      if (!result.hasNextPage) return entries;
      if (!result.endCursor)
        throw new Error('Workflow pagination returned no continuation cursor.');
      cursor = result.endCursor;
    }
    throw new Error(
      'Investigation history exceeds the 10,000-event POC limit. Narrow the server-side workspace before loading.',
    );
  }
  async append(event: CaseEvent) {
    this.guard();
    const value = eventSchema.parse(event);
    if (value.user_id !== this.identity()?.id) throw new Error('Investigation identity mismatch.');
    await this.client.data.InvestigationEvent.create({
      ...value,
      createdAt: new Date(value.createdAt),
    });
  }
}

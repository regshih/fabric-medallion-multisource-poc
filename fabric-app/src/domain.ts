import { z } from 'zod';

export const bands = ['High', 'Medium', 'Low'] as const;
export const statuses = ['Open', 'Investigating', 'Escalated', 'Resolved'] as const;
export type Band = (typeof bands)[number];
export type CaseStatus = (typeof statuses)[number];
const finite = z.coerce.number().finite();
export const profileSchema = z.object({
  CustomerID: z.string().regex(/^CUST-\d{6}$/),
  TransactionCount30D: finite.nonnegative(),
  TotalTransactionAmount30D: finite.nonnegative(),
  AverageTransactionRiskScore: finite.min(0).max(100),
  HighRiskTransactionCount: finite.nonnegative(),
  FailedLoginCount: finite.nonnegative(),
  DistinctDeviceCount: finite.nonnegative(),
  UntrustedDeviceCount: finite.nonnegative(),
  GeographicAnomalyCount: finite.nonnegative(),
  FraudAlertCount: finite.nonnegative(),
  CustomerRiskScore: finite.min(0).max(100),
  CustomerRiskBand: z.enum(bands),
  gold_loaded_at: z.string(),
  pipeline_run_id: z.string(),
});
export type Profile = z.infer<typeof profileSchema>;
export interface Transaction {
  CustomerID: string;
  TransactionID: string;
  TransactionTimestamp: string;
  Amount: number;
  Currency: string;
  Channel: string;
  RiskScore: number | null;
  TransactionStatus: string;
}
export interface Session {
  CustomerID: string;
  SessionID: string;
  LoginTimestamp: string;
  AuthenticationMethod: string;
  MfaUsed: boolean;
  FailedAttempts: number;
  Country: string;
}
export interface Alert {
  CustomerID: string;
  AlertID: string;
  CreatedTimestamp: string;
  Severity: string;
  Status: string;
  alertType: string;
  TransactionID: string | null;
}
export interface Detail {
  transactions: Transaction[];
  sessions: Session[];
  alerts: Alert[];
  capped: boolean;
}
export interface Quality {
  source: string;
  object: string;
  status: string;
  quarantine_count: number;
  pipeline_run_id: string;
  run_date: string;
}
export interface Snapshot {
  profiles: Profile[];
  quality: Quality[];
  fetchedAt: string;
  capped: boolean;
  qualityError?: string;
}
export interface Identity {
  id: string;
  email: string;
}
export const eventSchema = z.object({
  id: z.uuid(),
  caseId: z.uuid(),
  CustomerID: z.string().regex(/^CUST-\d{6}$/),
  user_id: z.string().min(1).max(255),
  eventType: z.enum(['created', 'updated', 'note']),
  status: z.enum(statuses),
  assignee: z.string().trim().min(1).max(120),
  note: z.string().trim().max(2000),
  createdAt: z.iso.datetime(),
});
export type CaseEvent = z.infer<typeof eventSchema>;
export interface Investigation {
  id: string;
  CustomerID: string;
  status: CaseStatus;
  assignee: string;
  createdAt: string;
  updatedAt: string;
  events: CaseEvent[];
}

export function reduceCases(events: CaseEvent[]): Investigation[] {
  const result = new Map<string, Investigation>();
  for (const event of [...events].sort(
    (a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id),
  )) {
    const current = result.get(event.caseId);
    if (event.eventType === 'created' && !current) {
      result.set(event.caseId, {
        id: event.caseId,
        CustomerID: event.CustomerID,
        status: event.status,
        assignee: event.assignee,
        createdAt: event.createdAt,
        updatedAt: event.createdAt,
        events: [event],
      });
    } else if (current && current.CustomerID === event.CustomerID) {
      current.events.push(event);
      current.updatedAt = event.createdAt;
      if (event.eventType === 'updated') {
        current.status = event.status;
        current.assignee = event.assignee;
      }
    }
  }
  return [...result.values()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function makeEvent(
  identity: Identity,
  profile: Profile,
  investigation?: Investigation,
  change?: Partial<Pick<CaseEvent, 'status' | 'assignee' | 'note'>>,
  noteOnly = false,
): CaseEvent {
  return eventSchema.parse({
    id: crypto.randomUUID(),
    caseId: investigation?.id ?? crypto.randomUUID(),
    CustomerID: profile.CustomerID,
    user_id: identity.id,
    eventType: investigation ? (noteOnly ? 'note' : 'updated') : 'created',
    status: change?.status ?? investigation?.status ?? 'Open',
    assignee: change?.assignee ?? investigation?.assignee ?? 'Unassigned',
    note: change?.note ?? '',
    createdAt: new Date().toISOString(),
  });
}

export function riskFactors(p: Profile) {
  return [
    {
      name: 'Transaction risk',
      value: p.AverageTransactionRiskScore * 0.45,
      max: 45,
      detail: `Average score ${p.AverageTransactionRiskScore.toFixed(1)} × 0.45`,
    },
    {
      name: 'Fraud alerts',
      value: Math.min(p.FraudAlertCount * 12, 24),
      max: 24,
      detail: `${p.FraudAlertCount} alerts · capped at 24`,
    },
    {
      name: 'Failed sign-ins',
      value: Math.min(p.FailedLoginCount * 2, 12),
      max: 12,
      detail: `${p.FailedLoginCount} failed attempts · capped at 12`,
    },
    {
      name: 'Untrusted devices',
      value: Math.min(p.UntrustedDeviceCount * 5, 10),
      max: 10,
      detail: `${p.UntrustedDeviceCount} devices · capped at 10`,
    },
    {
      name: 'Geographic signals',
      value: Math.min(p.GeographicAnomalyCount * 3, 9),
      max: 9,
      detail: `${p.GeographicAnomalyCount} non-US sessions · capped at 9`,
    },
  ];
}
export function freshness(value: string, now = Date.now()) {
  const time = Date.parse(
    value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z',
  );
  if (!Number.isFinite(time) || time > now + 300_000) return 'Unknown';
  return now - time <= 86_400_000 ? 'Within 24h' : 'Older than 24h';
}
export const number = (n: number) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n);
export function dateTime(value: string) {
  const timestamp = /Z$|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z';
  return Number.isFinite(Date.parse(timestamp))
    ? new Date(timestamp).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
    : 'Unavailable';
}

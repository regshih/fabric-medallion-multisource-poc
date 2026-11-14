import { profileSchema, type Snapshot, type Detail, type Profile } from './domain';

// Generated independently for the application. Matches the repository's Gold
// column contract and score formula; never represented as a cloud query result.
export const DEMO_AS_OF = '2026-09-01T15:42:00Z';
export const DEMO_IDENTITY = { id: 'demo-investigator', email: 'investigator@example.test' };
function rng(seed: number) {
  let value = seed;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}
export function buildDemo(): Snapshot {
  const random = rng(7341);
  const profiles = Array.from({ length: 120 }, (_, i) => {
    const high = i % 11 === 0;
    const average = high ? 91 + random() * 8 : 8 + random() * 69;
    const alerts = high ? 2 + (i % 3) : random() < 0.24 ? 1 : 0;
    const failed = high ? 7 : Math.floor(random() * 5);
    const devices = high ? 2 : random() < 0.3 ? 1 : 0;
    const geography = high ? 3 : random() < 0.22 ? 1 : 0;
    const score =
      Math.round(
        Math.min(
          100,
          average * 0.45 +
            Math.min(alerts * 12, 24) +
            Math.min(failed * 2, 12) +
            Math.min(devices * 5, 10) +
            Math.min(geography * 3, 9),
        ) * 100,
      ) / 100;
    return profileSchema.parse({
      CustomerID: `CUST-${String(i + 1).padStart(6, '0')}`,
      TransactionCount30D: 7 + Math.floor(random() * 75),
      TotalTransactionAmount30D: Math.round(random() * 65000 * 100) / 100,
      AverageTransactionRiskScore: Math.round(average * 100) / 100,
      HighRiskTransactionCount: high ? 6 : 0,
      FailedLoginCount: failed,
      DistinctDeviceCount: 1 + (i % 5),
      UntrustedDeviceCount: devices,
      GeographicAnomalyCount: geography,
      FraudAlertCount: alerts,
      CustomerRiskScore: score,
      CustomerRiskBand: score >= 80 ? 'High' : score >= 45 ? 'Medium' : 'Low',
      gold_loaded_at: DEMO_AS_OF,
      pipeline_run_id: 'synthetic-app-fixture-001',
    });
  }).sort((a, b) => b.CustomerRiskScore - a.CustomerRiskScore);
  return {
    profiles,
    fetchedAt: new Date().toISOString(),
    capped: false,
    quality: [
      ['databricks', 'transactions'],
      ['databricks', 'transaction_risk'],
      ['databricks', 'merchants'],
      ['cosmos', 'digitalSessions'],
      ['cosmos', 'devices'],
      ['cosmos', 'fraudAlerts'],
      ['cross_source', 'fraud_alerts_to_transactions'],
    ].map(([source, object]) => ({
      source,
      object,
      status: 'PASS',
      quarantine_count: 0,
      pipeline_run_id: 'synthetic-app-fixture-001',
      run_date: '2026-09-01',
    })),
  };
}
export function demoDetail(profile: Profile): Detail {
  const seed = Number(profile.CustomerID.slice(-6));
  const random = rng(seed);
  return {
    transactions: Array.from({ length: Math.min(profile.TransactionCount30D, 12) }, (_, i) => ({
      CustomerID: profile.CustomerID,
      TransactionID: `TXN-${String(seed * 100 + i).padStart(9, '0')}`,
      TransactionTimestamp: `2026-08-${String(31 - i).padStart(2, '0')}T14:20:00Z`,
      Amount: Math.round((20 + random() * 2400) * 100) / 100,
      Currency: i % 7 === 0 ? 'EUR' : 'USD',
      Channel: ['Mobile', 'Web', 'POS'][i % 3],
      RiskScore: Math.round(random() * 100),
      TransactionStatus: i % 6 === 0 ? 'Declined' : 'Approved',
    })),
    sessions: Array.from({ length: 6 }, (_, i) => ({
      CustomerID: profile.CustomerID,
      SessionID: `SESSION-${seed}-${i}`,
      LoginTimestamp: `2026-08-${31 - i}T09:30:00Z`,
      AuthenticationMethod: i % 2 ? 'Password' : 'Biometric',
      MfaUsed: i % 3 !== 0,
      FailedAttempts: i === 0 ? profile.FailedLoginCount : 0,
      Country: i === 0 && profile.GeographicAnomalyCount ? 'GB' : 'US',
    })),
    alerts: Array.from({ length: profile.FraudAlertCount }, (_, i) => ({
      CustomerID: profile.CustomerID,
      AlertID: `ALERT-${seed}-${i}`,
      CreatedTimestamp: `2026-08-31T1${i}:15:00Z`,
      Severity: profile.CustomerRiskBand === 'High' ? 'high' : 'medium',
      Status: i === 0 ? 'open' : 'investigating',
      alertType: i % 2 ? 'untrusted_device' : 'transaction_velocity',
      TransactionID: `TXN-${String(seed * 100 + i).padStart(9, '0')}`,
    })),
    capped: profile.TransactionCount30D > 12,
  };
}

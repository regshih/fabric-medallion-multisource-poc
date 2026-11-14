import { entity, role, text, int, decimal, boolean } from '@microsoft/rayfin-core';
import { Source } from '@microsoft/rayfin-connectors';

// SQL views intentionally have no declared primary keys. Never infer a PK from
// a field name. All exposed operations are read-only.
@entity()
@role('authenticated', ['read'])
export class CustomerProfile extends Source({ schema: 'risk_app', table: 'CustomerProfile' }) {
  @text() CustomerID!: string;
  @int() TransactionCount30D!: number;
  @decimal({ precision: 18, scale: 2 }) TotalTransactionAmount30D!: number;
  @decimal({ precision: 8, scale: 2 }) AverageTransactionRiskScore!: number;
  @int() HighRiskTransactionCount!: number;
  @int() FailedLoginCount!: number;
  @int() DistinctDeviceCount!: number;
  @int() UntrustedDeviceCount!: number;
  @int() GeographicAnomalyCount!: number;
  @int() FraudAlertCount!: number;
  @decimal({ precision: 8, scale: 2 }) CustomerRiskScore!: number;
  @text() CustomerRiskBand!: string;
  @text() gold_loaded_at!: string;
  @text() pipeline_run_id!: string;
}
@entity()
@role('authenticated', ['read'])
export class CustomerTransaction extends Source({
  schema: 'risk_app',
  table: 'CustomerTransaction',
}) {
  @text() CustomerID!: string;
  @text() TransactionID!: string;
  @text() TransactionTimestamp!: string;
  @decimal({ precision: 18, scale: 2 }) Amount!: number;
  @text() Currency!: string;
  @text() Channel!: string;
  @decimal({ precision: 8, scale: 2, optional: true }) RiskScore?: number;
  @text() TransactionStatus!: string;
}
@entity()
@role('authenticated', ['read'])
export class CustomerSession extends Source({ schema: 'risk_app', table: 'CustomerSession' }) {
  @text() CustomerID!: string;
  @text() SessionID!: string;
  @text() LoginTimestamp!: string;
  @text() AuthenticationMethod!: string;
  @boolean() MfaUsed!: boolean;
  @int() FailedAttempts!: number;
  @text() Country!: string;
}
@entity()
@role('authenticated', ['read'])
export class CustomerAlert extends Source({ schema: 'risk_app', table: 'CustomerAlert' }) {
  @text() CustomerID!: string;
  @text() AlertID!: string;
  @text() CreatedTimestamp!: string;
  @text() Severity!: string;
  @text() Status!: string;
  @text() alertType!: string;
  @text({ optional: true }) TransactionID?: string;
}
@entity()
@role('authenticated', ['read'])
export class QualityCheck extends Source({ schema: 'risk_app', table: 'QualityCheck' }) {
  @text() source!: string;
  @text() object!: string;
  @text() status!: string;
  @int() quarantine_count!: number;
  @text() pipeline_run_id!: string;
  @text() run_date!: string;
}

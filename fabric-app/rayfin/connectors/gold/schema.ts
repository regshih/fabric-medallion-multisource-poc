import type { GraphQLBackedConnector } from '@microsoft/rayfin-connector-fabric-graphql';
import type { ConnectorConfig } from '@microsoft/rayfin-connectors';
import {
  CustomerProfile,
  CustomerTransaction,
  CustomerSession,
  CustomerAlert,
  QualityCheck,
} from './entities.js';
export { CustomerProfile, CustomerTransaction, CustomerSession, CustomerAlert, QualityCheck };
export const connectorConfig = {
  connector: 'fabric-warehouse',
  operations: ['read'],
  entities: { CustomerProfile, CustomerTransaction, CustomerSession, CustomerAlert, QualityCheck },
} as const satisfies ConnectorConfig;
export type GoldSchema = GraphQLBackedConnector<
  {
    CustomerProfile: typeof CustomerProfile;
    CustomerTransaction: typeof CustomerTransaction;
    CustomerSession: typeof CustomerSession;
    CustomerAlert: typeof CustomerAlert;
    QualityCheck: typeof QualityCheck;
  },
  typeof connectorConfig
>;

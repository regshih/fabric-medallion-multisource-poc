import {
  eventSchema,
  type CaseEvent,
  type Identity,
  type Profile,
  type Snapshot,
  type Detail,
} from './domain';
import { buildDemo, demoDetail, DEMO_IDENTITY } from './demo';

export interface Repository {
  readonly mode: 'demo' | 'live';
  identity(): Identity | null;
  signIn(): Promise<void>;
  signOut(): Promise<void>;
  snapshot(): Promise<Snapshot>;
  profile(customerId: string): Promise<Profile | null>;
  detail(profile: Profile): Promise<Detail>;
  events(): Promise<CaseEvent[]>;
  append(event: CaseEvent): Promise<void>;
}

function openDemoDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('signal-fabric-demo-v1', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('events', { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(
        new Error('Demo storage is unavailable. Enable browser storage to save investigations.'),
      );
    request.onblocked = () =>
      reject(new Error('Close other demo tabs to finish upgrading local storage.'));
  });
}
export class DemoRepository implements Repository {
  readonly mode = 'demo';
  identity() {
    return DEMO_IDENTITY;
  }
  async signIn() {
    /* An explicit synthetic persona; no authentication claim. */
  }
  async signOut() {
    /* Demo has no Entra session. */
  }
  async snapshot() {
    return buildDemo();
  }
  async profile(customerId: string) {
    return buildDemo().profiles.find((p) => p.CustomerID === customerId) ?? null;
  }
  async detail(profile: Profile) {
    return demoDetail(profile);
  }
  async events() {
    const db = await openDemoDb();
    try {
      const values = await new Promise<unknown[]>((resolve, reject) => {
        const request = db.transaction('events').objectStore('events').getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(new Error('Could not read local investigations.'));
      });
      return eventSchema.array().parse(values);
    } finally {
      db.close();
    }
  }
  async append(event: CaseEvent) {
    const value = eventSchema.parse(event);
    if (value.user_id !== DEMO_IDENTITY.id)
      throw new Error('The event does not belong to the demo investigator.');
    const db = await openDemoDb();
    try {
      await new Promise<void>((resolve, reject) => {
        const tx = db.transaction('events', 'readwrite');
        tx.objectStore('events').add(value);
        tx.oncomplete = () => resolve();
        tx.onerror = () =>
          reject(new Error('Could not save investigation. No success has been recorded.'));
        tx.onabort = () => reject(new Error('The investigation write was aborted.'));
      });
    } finally {
      db.close();
    }
  }
}

export async function createRepository(): Promise<Repository> {
  const mode = import.meta.env.VITE_DATA_MODE ?? 'demo';
  if (mode === 'demo') return new DemoRepository();
  if (mode !== 'live') throw new Error('VITE_DATA_MODE must be demo or live.');
  const { LiveRepository } = await import('./live');
  return new LiveRepository().initialize();
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  ExternalLink,
  Filter,
  GitBranch,
  LayoutDashboard,
  ListFilter,
  LoaderCircle,
  LogOut,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldEllipsis,
  Sparkles,
  UserRound,
  Workflow,
  X,
} from 'lucide-react';
import {
  bands,
  dateTime,
  freshness,
  makeEvent,
  number,
  reduceCases,
  riskFactors,
  statuses,
  type CaseEvent,
  type CaseStatus,
  type Detail,
  type Investigation,
  type Profile,
  type Snapshot,
} from './domain';
import type { Repository } from './repository';

type View = 'overview' | 'explorer' | 'investigations' | 'journey';
const views = [
  { id: 'overview' as const, label: 'Overview', icon: LayoutDashboard },
  { id: 'explorer' as const, label: 'Customer explorer', icon: Search },
  { id: 'investigations' as const, label: 'Investigations', icon: ShieldEllipsis },
  { id: 'journey' as const, label: 'Data journey', icon: GitBranch },
];
const messages: Record<View, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: 'RISK OPERATIONS',
    title: 'From signal to action.',
    description: 'A connected view of customer risk. The context to investigate it.',
  },
  explorer: {
    eyebrow: 'CUSTOMER INTELLIGENCE',
    title: 'Follow the signals.',
    description:
      'Explore the loaded customer cohort, then open the complete investigation context.',
  },
  investigations: {
    eyebrow: 'YOUR WORKSPACE',
    title: 'Move the work forward.',
    description: 'A persistent investigation trail, from the first question to resolution.',
  },
  journey: {
    eyebrow: 'ARCHITECTURE & TRUST',
    title: 'Know where it comes from.',
    description: 'Keep the existing data platform. Put its curated intelligence to work.',
  },
};
function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The operation failed. Please retry.';
}
export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value.toLowerCase().replaceAll(' ', '-')}`}>
      {value === 'High' && <span className="badge-dot" />}
      {value}
    </span>
  );
}

export default function App({ repository }: { repository: Repository }) {
  const [view, setView] = useState<View>('overview');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [events, setEvents] = useState<CaseEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [identity, setIdentity] = useState(repository.identity());
  const [selected, setSelected] = useState<Profile | null>(null);
  const [search, setSearch] = useState('');
  const [band, setBand] = useState('All risk levels');
  const cases = useMemo(() => reduceCases(events), [events]);
  const openCases = cases.filter((c) => c.status !== 'Resolved');
  const refresh = useCallback(async () => {
    if (!repository.identity()) return;
    setBusy(true);
    setError('');
    try {
      const [data, entries] = await Promise.all([repository.snapshot(), repository.events()]);
      setSnapshot(data);
      setEvents(entries);
      setIdentity(repository.identity());
    } catch (e) {
      setError(errorMessage(e));
      if (!repository.identity()) {
        setIdentity(null);
        setSnapshot(null);
        setEvents([]);
        setSelected(null);
      }
    } finally {
      setBusy(false);
    }
  }, [repository]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(''), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  async function signIn() {
    setError('');
    try {
      await repository.signIn();
      setIdentity(repository.identity());
      await refresh();
    } catch (e) {
      setIdentity(null);
      setError(errorMessage(e));
    }
  }
  async function signOut() {
    setSelected(null);
    setSnapshot(null);
    setEvents([]);
    setIdentity(null);
    try {
      await repository.signOut();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function saveEvent(event: CaseEvent) {
    await repository.append(event);
    // Keep the acknowledged write even if a subsequent fetch fails.
    setEvents((current) =>
      current.some((e) => e.id === event.id) ? current : [...current, event],
    );
    setNotice(
      event.eventType === 'created'
        ? 'Investigation opened. Your work is saved.'
        : event.eventType === 'note'
          ? 'Investigation note saved.'
          : 'Investigation updated.',
    );
  }
  const profiles = snapshot?.profiles ?? [];
  const closeDrawer = useCallback(() => setSelected(null), []);
  async function openInvestigation(item: Investigation) {
    setError('');
    try {
      const profile =
        profiles.find((p) => p.CustomerID === item.CustomerID) ??
        (await repository.profile(item.CustomerID));
      if (!profile)
        throw new Error(
          'This customer is unavailable under current source permissions. Your investigation history is retained.',
        );
      setSelected(profile);
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  function investigateHigh() {
    setBand('High');
    setSearch('');
    setView('explorer');
  }
  function goExplorer(value = '') {
    setSearch(value);
    setBand('All risk levels');
    setView('explorer');
  }
  const high = profiles.filter((p) => p.CustomerRiskBand === 'High');
  const title = messages[view];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView('overview');
          }}
          aria-label="Signal overview"
        >
          <span className="brand-mark">
            <Activity size={25} />
          </span>
          <span>
            signal<span className="brand-period">.</span>
          </span>
        </a>
        <div className="workspace-label">FABRIC RISK WORKBENCH</div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {views.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? 'active' : ''}`}
              onClick={() => setView(item.id)}
              aria-current={view === item.id ? 'page' : undefined}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {item.id === 'investigations' && openCases.length > 0 && (
                <span className="nav-count">{openCases.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="source-card">
            <span className="source-icon">
              <Database size={19} />
            </span>
            <div>
              <strong>Built on your data</strong>
              <p>Databricks + Fabric</p>
            </div>
            <span className="tiny-dot" />
          </div>
          <button className="sidebar-help" onClick={() => setView('journey')}>
            <CircleHelp size={17} /> Architecture & demo guide <ArrowUpRight size={14} />
          </button>
          <div className="profile-avatar">
            <span className="avatar">
              {repository.mode === 'demo' ? 'DI' : <UserRound size={18} />}
            </span>
            <div>
              <strong>
                {repository.mode === 'demo'
                  ? 'Demo investigator'
                  : (identity?.email ?? 'Not signed in')}
              </strong>
              <small>
                {repository.mode === 'demo' ? 'Local synthetic persona' : 'Microsoft Entra ID'}
              </small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>{views.find((v) => v.id === view)?.label}</strong>
          </div>
          <div className="topbar-right">
            <span className={`mode-pill ${repository.mode}`}>
              <span />
              {repository.mode === 'demo' ? 'Synthetic demo' : 'Live Fabric'}
            </span>
            <span className="top-divider" />
            <span className="powered">
              <span className="fabric-glyph">▰</span> Microsoft Fabric
            </span>
            {repository.mode === 'live' && identity && (
              <button className="icon-button" title="Sign out" onClick={() => void signOut()}>
                <LogOut size={18} />
              </button>
            )}
          </div>
        </header>
        <main id="main-content">
          <div className={`environment-banner ${repository.mode}`}>
            <ShieldCheck size={16} />
            <span>
              {repository.mode === 'demo' ? (
                <>
                  Synthetic demo data · fixture dated Sep 1, 2026 · workflows saved in this browser.
                  No live connection.
                </>
              ) : (
                <>
                  Live connector · source permissions apply · workflows stored in the app database.
                </>
              )}
            </span>
            <button onClick={() => setView('journey')}>
              View data journey <ArrowRight size={14} />
            </button>
          </div>
          <div className="page-heading">
            <div>
              <div className="eyebrow">{title.eyebrow}</div>
              <h1>{title.title}</h1>
              <p>{title.description}</p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                disabled={busy || !identity}
                onClick={() => void refresh()}
              >
                <RefreshCw size={15} className={busy ? 'spin' : ''} /> Refresh
              </button>
              {view !== 'journey' && (
                <button
                  className="button primary"
                  onClick={() => goExplorer()}
                  disabled={!snapshot}
                >
                  <Plus size={16} /> Open investigation
                </button>
              )}
            </div>
          </div>
          {error && (
            <div role="alert" className="error-box">
              <strong>Action needed</strong>
              <span>{error}</span>
              <button onClick={() => void refresh()} disabled={busy || !identity}>
                Retry
              </button>
            </div>
          )}
          {!identity ? (
            <div className="sign-in-card panel">
              <ShieldCheck size={42} />
              <h2>Your identity. Your investigation workspace.</h2>
              <p>
                Sign in with Microsoft Fabric to read permitted Gold data and access your saved
                investigations.
              </p>
              <button className="button primary" onClick={() => void signIn()}>
                Sign in with Fabric <ArrowRight size={17} />
              </button>
            </div>
          ) : busy && !snapshot ? (
            <div className="loading-state" role="status">
              <LoaderCircle className="spin" size={28} />
              <h2>Connecting the signals…</h2>
              <p>Reading customer context and your saved investigations.</p>
            </div>
          ) : snapshot ? (
            <>
              {view === 'overview' && (
                <>
                  <div className="scope-line">
                    <span>
                      <span className="tiny-dot" /> {number(profiles.length)} customers in loaded
                      cohort{snapshot.capped ? ' · bounded by connector limit' : ''}
                    </span>
                    <span>Refreshed {dateTime(snapshot.fetchedAt)}</span>
                  </div>
                  <div className="kpi-grid">
                    <Kpi
                      label="Customers in view"
                      value={number(profiles.length)}
                      icon={<UserRound size={19} />}
                      detail="Loaded cohort · all risk levels"
                    />
                    <Kpi
                      label="High-risk customers"
                      value={number(high.length)}
                      icon={<ShieldEllipsis size={19} />}
                      detail={`${profiles.length ? ((high.length / profiles.length) * 100).toFixed(1) : '0'}% of loaded cohort`}
                      accent
                    />
                    <Kpi
                      label="Fraud signals"
                      value={number(profiles.reduce((s, p) => s + p.FraudAlertCount, 0))}
                      icon={<Activity size={19} />}
                      detail="Source alert count · loaded cohort"
                    />
                    <Kpi
                      label="My open investigations"
                      value={number(openCases.length)}
                      icon={<Workflow size={19} />}
                      detail={`${cases.filter((c) => c.status === 'Resolved').length} resolved · app workflow data`}
                    />
                  </div>
                  <div className="dashboard-middle">
                    <section className="panel distribution-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Customer risk landscape</h2>
                          <p>Distribution of the loaded customer cohort</p>
                        </div>
                        <span className="small-tag">Source score / 100</span>
                      </div>
                      <RiskChart profiles={profiles} />
                      <div className="chart-legend">
                        {bands.map((b) => (
                          <button
                            key={b}
                            onClick={() => {
                              setBand(b);
                              setView('explorer');
                            }}
                          >
                            <span className={`legend-dot ${b.toLowerCase()}`} />
                            {b}
                            <strong>
                              {profiles.filter((p) => p.CustomerRiskBand === b).length}
                            </strong>
                          </button>
                        ))}
                      </div>
                    </section>
                    <section className="action-card">
                      <span className="action-symbol">
                        <Sparkles size={23} />
                      </span>
                      <span className="eyebrow">NEXT BEST ACTION</span>
                      <h2>
                        Turn a risk signal
                        <br />
                        into a resolution.
                      </h2>
                      <p>
                        {high.length
                          ? `${high.length} customers in this cohort have a high risk score. Bring transactions and digital behavior into one investigation.`
                          : 'Review source signals and capture the context behind your next investigation.'}
                      </p>
                      <button onClick={investigateHigh}>
                        Review high-risk customers <ArrowRight size={17} />
                      </button>
                      <div className="action-footnote">
                        <ShieldCheck size={14} /> Explainable heuristic · synthetic source data
                      </div>
                    </section>
                  </div>
                  <div className="dashboard-bottom">
                    <section className="panel priority-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Customers to review</h2>
                          <p>Highest source scores in your loaded cohort</p>
                        </div>
                        <button className="text-button" onClick={() => goExplorer()}>
                          Explore all <ArrowRight size={15} />
                        </button>
                      </div>
                      <CustomerTable
                        profiles={[...profiles]
                          .sort((a, b) => b.CustomerRiskScore - a.CustomerRiskScore)
                          .slice(0, 5)}
                        cases={cases}
                        onSelect={setSelected}
                        compact
                      />
                    </section>
                    <section className="panel health-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Data confidence</h2>
                          <p>Evidence, with its boundaries</p>
                        </div>
                        <ShieldCheck size={20} />
                      </div>
                      <Health snapshot={snapshot} />
                      <button
                        className="text-button health-link"
                        onClick={() => setView('journey')}
                      >
                        Trace the data journey <ArrowRight size={15} />
                      </button>
                    </section>
                  </div>
                </>
              )}
              {view === 'explorer' && (
                <Explorer
                  profiles={profiles}
                  cases={cases}
                  onSelect={setSelected}
                  search={search}
                  setSearch={setSearch}
                  band={band}
                  setBand={setBand}
                  capped={snapshot.capped}
                />
              )}
              {view === 'investigations' && (
                <Investigations
                  cases={cases}
                  profiles={profiles}
                  onOpen={openInvestigation}
                  onExplore={goExplorer}
                />
              )}
              {view === 'journey' && <Journey snapshot={snapshot} mode={repository.mode} />}
            </>
          ) : (
            !busy && (
              <div className="empty-state panel">
                <Database size={32} />
                <h2>No data loaded</h2>
                <p>
                  Review the connection error above, then refresh. Live errors never switch to demo
                  data.
                </p>
              </div>
            )
          )}
          <footer>
            <span>Signal / Fabric Risk Workbench</span>
            <span>Customer-ready POC · synthetic banking source · no automated risk decisions</span>
          </footer>
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check size={18} />
          {notice}
        </div>
      )}
      {selected && identity && (
        <CustomerDrawer
          profile={selected}
          repository={repository}
          investigation={cases.find((c) => c.CustomerID === selected.CustomerID)}
          onClose={closeDrawer}
          onSave={saveEvent}
        />
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  icon,
  detail,
  accent = false,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  detail: string;
  accent?: boolean;
}) {
  return (
    <section className={`kpi-card ${accent ? 'accent' : ''}`}>
      <div className="kpi-label">
        {label}
        <span>{icon}</span>
      </div>
      <strong className="kpi-value">{value}</strong>
      <small>
        {accent && <ArrowDownRight size={13} />} {detail}
      </small>
    </section>
  );
}
function RiskChart({ profiles }: { profiles: Profile[] }) {
  const counts = Array.from(
    { length: 10 },
    (_, i) =>
      profiles.filter((p) => Math.min(9, Math.floor(p.CustomerRiskScore / 10)) === i).length,
  );
  const max = Math.max(...counts, 1);
  return (
    <div
      className="risk-chart"
      role="img"
      aria-label={`Risk distribution: ${counts.map((n, i) => `${i * 10} to ${i === 9 ? 100 : i * 10 + 9}: ${n} customers`).join('; ')}`}
    >
      <div className="chart-grid">
        {[1, 0.75, 0.5, 0.25].map((n) => (
          <div key={n}>
            <span>{Math.round(max * n)}</span>
          </div>
        ))}
      </div>
      <div className="chart-bars">
        {counts.map((n, i) => (
          <div className="chart-column" key={i}>
            <span
              className={`bar ${i >= 8 ? 'high' : i >= 4 ? 'medium' : 'low'}`}
              style={{ height: `${Math.max(1.5, (n / max) * 100)}%` }}
            >
              <span>{n}</span>
            </span>
            <small>{i * 10}</small>
          </div>
        ))}
      </div>
      <span className="chart-axis-label">Customer risk score →</span>
    </div>
  );
}
function Health({ snapshot }: { snapshot: Snapshot }) {
  const failures = snapshot.quality.filter((q) => q.status !== 'PASS').length;
  const loaded = snapshot.profiles.map((p) => p.gold_loaded_at).sort()[0];
  const runs = new Set(snapshot.profiles.map((p) => p.pipeline_run_id));
  const sameRun =
    runs.size === 1 &&
    snapshot.quality.length > 0 &&
    snapshot.quality.every((q) => runs.has(q.pipeline_run_id));
  const qualityText = snapshot.qualityError
    ? 'Query unavailable · not verified'
    : snapshot.quality.length
      ? `${snapshot.quality.length - failures}/${snapshot.quality.length} checks pass · ${sameRun ? 'same run' : 'run mismatch'}`
      : 'No evidence returned';
  return (
    <div className="health-rows">
      <div>
        <span className={`health-icon ${failures || !sameRun ? 'warning' : ''}`}>
          <ShieldCheck size={16} />
        </span>
        <div>
          <strong>Reconciliation</strong>
          <small>{qualityText}</small>
        </div>
        <Badge value={sameRun && !failures ? 'PASS' : 'Review'} />
      </div>
      <div>
        <span className="health-icon warning">
          <Clock3 size={16} />
        </span>
        <div>
          <strong>Gold freshness</strong>
          <small>{loaded ? `Oldest load ${dateTime(loaded)}` : 'No Gold timestamps'}</small>
        </div>
        <span className="health-state">{loaded ? freshness(loaded) : 'Unknown'}</span>
      </div>
      <div>
        <span className="health-icon">
          <GitBranch size={16} />
        </span>
        <div>
          <strong>Lineage</strong>
          <small>
            {runs.size === 1
              ? 'One run in loaded cohort'
              : `${runs.size} runs · review mixed snapshots`}
          </small>
        </div>
        <span className="health-state">{runs.size === 1 ? 'Available' : 'Review'}</span>
      </div>
    </div>
  );
}

function CustomerTable({
  profiles,
  cases,
  onSelect,
  compact = false,
}: {
  profiles: Profile[];
  cases: Investigation[];
  onSelect: (p: Profile) => void;
  compact?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table className="customer-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th>Risk score</th>
            <th>Risk level</th>
            {!compact && (
              <>
                <th>Transactions</th>
                <th>Fraud alerts</th>
              </>
            )}
            <th>Investigation</th>
            <th>
              <span className="sr-only">Open customer</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((p, i) => {
            const item = cases.find((c) => c.CustomerID === p.CustomerID);
            return (
              <tr key={p.CustomerID}>
                <td>
                  <button className="customer-link" onClick={() => onSelect(p)}>
                    <span className={`customer-avatar tint-${i % 3}`}>
                      <UserRound size={15} />
                    </span>
                    <span>
                      {p.CustomerID}
                      <small>Retail banking</small>
                    </span>
                  </button>
                </td>
                <td>
                  <div className="score-cell">
                    <strong>{p.CustomerRiskScore.toFixed(1)}</strong>
                    <span>
                      <i
                        className={p.CustomerRiskBand.toLowerCase()}
                        style={{ width: `${p.CustomerRiskScore}%` }}
                      />
                    </span>
                  </div>
                </td>
                <td>
                  <Badge value={p.CustomerRiskBand} />
                </td>
                {!compact && (
                  <>
                    <td>{number(p.TransactionCount30D)}</td>
                    <td>
                      <span className={p.FraudAlertCount ? 'alert-number' : 'muted'}>
                        {p.FraudAlertCount}
                      </span>
                    </td>
                  </>
                )}
                <td>
                  {item ? <Badge value={item.status} /> : <span className="muted">Not opened</span>}
                </td>
                <td>
                  <button
                    className="icon-button"
                    onClick={() => onSelect(p)}
                    aria-label={`Open ${p.CustomerID}`}
                  >
                    <ArrowUpRight size={17} />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!profiles.length && <div className="empty-inline">No customers match these filters.</div>}
    </div>
  );
}
function Explorer({
  profiles,
  cases,
  onSelect,
  search,
  setSearch,
  band,
  setBand,
  capped,
}: {
  profiles: Profile[];
  cases: Investigation[];
  onSelect: (p: Profile) => void;
  search: string;
  setSearch: (v: string) => void;
  band: string;
  setBand: (v: string) => void;
  capped: boolean;
}) {
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState('score');
  const filtered = useMemo(
    () =>
      profiles
        .filter(
          (p) =>
            p.CustomerID.toLowerCase().includes(search.trim().toLowerCase()) &&
            (band === 'All risk levels' || p.CustomerRiskBand === band),
        )
        .sort((a, b) =>
          sort === 'score'
            ? b.CustomerRiskScore - a.CustomerRiskScore
            : sort === 'alerts'
              ? b.FraudAlertCount - a.FraudAlertCount
              : a.CustomerID.localeCompare(b.CustomerID),
        ),
    [profiles, search, band, sort],
  );
  const safePage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 12) - 1));
  return (
    <section className="panel explorer-panel">
      <div className="panel-heading">
        <div>
          <h2>
            Customer explorer <span className="count-pill">{profiles.length}</span>
          </h2>
          <p>
            {capped
              ? 'Bounded live cohort. Search and KPIs apply only to loaded rows.'
              : 'Search and filters apply to the loaded cohort.'}
          </p>
        </div>
        <span className="small-tag">
          <Database size={12} /> Gold / AggCustomerRiskProfile
        </span>
      </div>
      <div className="table-toolbar">
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label="Search customers"
            placeholder="Search customer ID…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
          {search && (
            <button
              onClick={() => {
                setSearch('');
                setPage(0);
              }}
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </label>
        <label className="select-filter">
          <Filter size={15} />
          <select
            aria-label="Risk level"
            value={band}
            onChange={(e) => {
              setBand(e.target.value);
              setPage(0);
            }}
          >
            <option>All risk levels</option>
            {bands.map((b) => (
              <option key={b}>{b}</option>
            ))}
          </select>
        </label>
        <label className="select-filter">
          <ListFilter size={16} />
          <select
            aria-label="Sort customers"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(0);
            }}
          >
            <option value="score">Highest risk first</option>
            <option value="alerts">Most alerts first</option>
            <option value="customer">Customer ID</option>
          </select>
        </label>
      </div>
      <CustomerTable
        profiles={filtered.slice(safePage * 12, safePage * 12 + 12)}
        cases={cases}
        onSelect={onSelect}
      />
      <div className="pagination">
        <span>
          {filtered.length ? safePage * 12 + 1 : 0}–{Math.min(filtered.length, safePage * 12 + 12)}{' '}
          of {number(filtered.length)} matching customers
        </span>
        <div>
          <button
            className="icon-button"
            disabled={!safePage}
            onClick={() => setPage(safePage - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft size={17} />
          </button>
          <span>
            Page {safePage + 1} of {Math.max(1, Math.ceil(filtered.length / 12))}
          </span>
          <button
            className="icon-button"
            disabled={(safePage + 1) * 12 >= filtered.length}
            onClick={() => setPage(safePage + 1)}
            aria-label="Next page"
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
    </section>
  );
}
function Investigations({
  cases,
  profiles,
  onOpen,
  onExplore,
}: {
  cases: Investigation[];
  profiles: Profile[];
  onOpen: (c: Investigation) => Promise<void>;
  onExplore: (s?: string) => void;
}) {
  const [status, setStatus] = useState('All statuses');
  const filtered = cases.filter((c) => status === 'All statuses' || c.status === status);
  return (
    <>
      <div className="workflow-notice">
        <ShieldCheck size={19} />
        <div>
          <strong>Your investigation workspace</strong>
          <p>
            Records are private to the signed-in investigator. Assignment is a routing label; it
            does not grant another person access.
          </p>
        </div>
      </div>
      <div className="case-summary">
        {statuses.map((s) => (
          <button
            key={s}
            className={status === s ? 'selected' : ''}
            onClick={() => setStatus(status === s ? 'All statuses' : s)}
          >
            <span>{s}</span>
            <strong>{cases.filter((c) => c.status === s).length}</strong>
          </button>
        ))}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Investigation queue</h2>
            <p>Append-only activity history · {cases.length} investigations</p>
          </div>
          <label className="select-filter">
            <Filter size={15} />
            <select
              aria-label="Investigation status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option>All statuses</option>
              {statuses.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        {filtered.length ? (
          <div className="case-list">
            {filtered.map((c) => {
              const profile = profiles.find((p) => p.CustomerID === c.CustomerID);
              return (
                <button className="case-row" key={c.id} onClick={() => void onOpen(c)}>
                  <span className="case-icon">
                    <Workflow size={20} />
                  </span>
                  <div>
                    <strong>{c.CustomerID}</strong>
                    <small>
                      INV-{c.id.slice(0, 8).toUpperCase()} · {c.assignee}
                    </small>
                  </div>
                  <Badge value={c.status} />
                  <span className="case-note-count">
                    <MessageSquare size={14} />
                    {c.events.filter((e) => e.note).length}
                  </span>
                  <span className="case-updated">
                    {dateTime(c.updatedAt)}
                    {!profile && <small>Outside loaded cohort</small>}
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <span className="empty-icon">
              <Workflow size={28} />
            </span>
            <h2>
              {cases.length
                ? 'No investigations in this status'
                : 'A signal is only the beginning.'}
            </h2>
            <p>
              {cases.length
                ? 'Choose another status to review your queue.'
                : 'Open a customer, gather the context, and start your first investigation.'}
            </p>
            <button className="button primary" onClick={() => onExplore()}>
              Explore customers <ArrowRight size={16} />
            </button>
          </div>
        )}
      </section>
    </>
  );
}

function Journey({ snapshot, mode }: { snapshot: Snapshot; mode: 'live' | 'demo' }) {
  const [step, setStep] = useState(3);
  const steps = [
    {
      title: 'Source systems',
      label: 'AZURE',
      icon: Database,
      text: 'Azure Databricks retains the transaction, risk and merchant Delta tables in Unity Catalog. Cosmos DB supplies sessions, devices and fraud alerts.',
    },
    {
      title: 'Bronze access',
      label: 'CONNECT',
      icon: GitBranch,
      text: 'The Databricks mirrored catalog synchronizes metadata and references source Delta through OneLake shortcuts. Cosmos mirroring creates a physical Delta replica. These are different mechanisms.',
    },
    {
      title: 'Silver quality',
      label: 'CONFORM',
      icon: Filter,
      text: 'Existing Fabric notebooks normalize names and types, deduplicate, validate relationships, and quarantine invalid records. Source and load lineage are retained.',
    },
    {
      title: 'Gold intelligence',
      label: 'CURATE',
      icon: Sparkles,
      text: 'Existing Fabric Gold holds the star schema and cross-source customer risk profile. Read-only app serving views preserve Warehouse RLS. Gold is built in Fabric; Databricks transformations are preserved.',
    },
    {
      title: 'Signal workbench',
      label: 'ACT',
      icon: Workflow,
      text: 'Rayfin reads permitted data through a delegated, read-only Warehouse connector. Investigation events live in a separate, app-owned SQL database, with owner policies. The demo uses IndexedDB in this browser.',
    },
  ];
  return (
    <>
      <section className="panel journey-panel">
        <div className="panel-heading">
          <div>
            <h2>An extension, without a platform rebuild.</h2>
            <p>Your medallion architecture stays the source of analytical truth.</p>
          </div>
          <span className="small-tag">Databricks → Fabric → App</span>
        </div>
        <div className="journey-steps">
          {steps.map((s, i) => (
            <div className="journey-step-wrap" key={s.title}>
              <button
                className={`journey-step ${i === step ? 'selected' : ''}`}
                onClick={() => setStep(i)}
              >
                <span className="step-number">0{i + 1}</span>
                <s.icon size={27} />
                <small>{s.label}</small>
                <strong>{s.title}</strong>
              </button>
              {i !== 4 && <ArrowRight size={18} className="journey-arrow" />}
            </div>
          ))}
        </div>
        <div className="journey-description">
          <span className="step-description-icon">
            {(() => {
              const Icon = steps[step].icon;
              return <Icon size={24} />;
            })()}
          </span>
          <div>
            <h3>{steps[step].title}</h3>
            <p>{steps[step].text}</p>
          </div>
        </div>
      </section>
      <div className="journey-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Trust boundaries</h2>
              <p>Designed to keep analytical data separate from action</p>
            </div>
            <ShieldCheck size={21} />
          </div>
          <div className="boundary-list">
            <div>
              <Check size={17} />
              <p>
                <strong>Gold access is read-only.</strong> App connector operations are restricted
                to read. No app action updates Databricks, Cosmos or Gold records.
              </p>
            </div>
            <div>
              <Check size={17} />
              <p>
                <strong>Source authorization stays explicit.</strong> Live Warehouse access uses
                delegated identity. App sign-in is Fabric SSO. App event policies restrict rows to
                their creator.
              </p>
            </div>
            <div>
              <Check size={17} />
              <p>
                <strong>Signals explain, people decide.</strong> Risk weights reproduce the existing
                synthetic heuristic. Geographic signals mean non-US sessions, not proven fraud.
              </p>
            </div>
            <div>
              <Check size={17} />
              <p>
                <strong>No hidden substitutions.</strong> Demo mode is selected at build time. A
                live connector failure remains visible and never returns fixtures.
              </p>
            </div>
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Connection & freshness</h2>
              <p>
                {mode === 'demo'
                  ? 'Demonstration fixture · not a cloud probe'
                  : 'Runtime evidence for retrieved rows'}
              </p>
            </div>
            <Database size={20} />
          </div>
          <Health snapshot={snapshot} />
          <div className="connection-note">
            <strong>{mode === 'demo' ? 'Local demo is ready' : 'Live Fabric mode'}</strong>
            <p>
              {mode === 'demo'
                ? 'Deploy only to an approved Fabric workspace after enabling the Preview workload and validating delegated access. Local workflows persist in this browser.'
                : 'The loaded cohort is bounded. Data quality checks refer to the latest retrieved pipeline run, not to an assurance of real-time source health.'}
            </p>
          </div>
        </section>
      </div>
      <section className="panel quality-panel">
        <div className="panel-heading">
          <div>
            <h2>Reconciliation evidence</h2>
            <p>
              {snapshot.qualityError ??
                'Latest retrieved run · source counts and relationship checks'}
            </p>
          </div>
          <span className="small-tag">
            {mode === 'demo' ? 'Synthetic fixture' : 'Read-only source'}
          </span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Object</th>
                <th>Result</th>
                <th>Quarantined</th>
                <th>Run date</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.quality.map((q) => (
                <tr key={`${q.source}-${q.object}`}>
                  <td>{q.source}</td>
                  <td>{q.object}</td>
                  <td>
                    <Badge value={q.status} />
                  </td>
                  <td>{q.quarantine_count}</td>
                  <td>{q.run_date.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!snapshot.quality.length && (
            <div className="empty-inline">Quality evidence is unavailable.</div>
          )}
        </div>
      </section>
      <div className="docs-links">
        <a
          href="https://learn.microsoft.com/en-us/fabric/apps/overview"
          target="_blank"
          rel="noreferrer"
        >
          Fabric Apps documentation <ExternalLink size={14} />
        </a>
        <a
          href="https://github.com/regshih/fabric-medallion-multisource-poc"
          target="_blank"
          rel="noreferrer"
        >
          Source architecture <ExternalLink size={14} />
        </a>
      </div>
    </>
  );
}

function CustomerDrawer({
  profile: p,
  repository,
  investigation,
  onClose,
  onSave,
}: {
  profile: Profile;
  repository: Repository;
  investigation?: Investigation;
  onClose: () => void;
  onSave: (e: CaseEvent) => Promise<void>;
}) {
  const [tab, setTab] = useState('Signals');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailError, setDetailError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [note, setNote] = useState('');
  const [status, setStatus] = useState<CaseStatus>(investigation?.status ?? 'Open');
  const [assignee, setAssignee] = useState(investigation?.assignee ?? 'Unassigned');
  const dialog = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement;
    dialog.current?.focus();
    const before = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    function key(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Tab') {
        const nodes = [
          ...(dialog.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input, textarea, select, a[href]',
          ) ?? []),
        ];
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first || document.activeElement === dialog.current)
        ) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener('keydown', key);
    return () => {
      document.body.style.overflow = before;
      document.removeEventListener('keydown', key);
      previousFocus.current?.focus();
    };
  }, [onClose]);
  useEffect(() => {
    let cancelled = false;
    repository
      .detail(p)
      .then((result) => {
        if (!cancelled) setDetail(result);
      })
      .catch((e) => {
        if (!cancelled) setDetailError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [p, repository]);
  async function save(noteOnly = false) {
    const identity = repository.identity();
    if (!identity) {
      setSaveError('Sign in again before saving.');
      return;
    }
    setSaving(true);
    setSaveError('');
    try {
      await onSave(makeEvent(identity, p, investigation, { status, assignee, note }, noteOnly));
      setNote('');
    } catch (e) {
      setSaveError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }
  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
    >
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="customer-title"
        tabIndex={-1}
        className="customer-drawer"
      >
        <div className="drawer-topline">
          <span>CUSTOMER INVESTIGATION</span>
          <button
            className="icon-button"
            aria-label="Close customer details"
            onClick={onClose}
            disabled={saving}
          >
            <X size={21} />
          </button>
        </div>
        <div className="drawer-header">
          <span className="large-avatar">
            <UserRound size={27} />
          </span>
          <div>
            <h2 id="customer-title">{p.CustomerID}</h2>
            <p>
              Retail banking ·{' '}
              {repository.mode === 'demo' ? 'synthetic app fixture' : 'synthetic source in Fabric'}
            </p>
          </div>
          <Badge value={p.CustomerRiskBand} />
        </div>
        <div className="drawer-risk">
          <div>
            <span>Customer risk score</span>
            <strong>
              {p.CustomerRiskScore.toFixed(1)}
              <small>/ 100</small>
            </strong>
          </div>
          <div
            className="risk-circle"
            style={{ '--risk': `${p.CustomerRiskScore}%` } as React.CSSProperties}
          >
            <ShieldEllipsis size={26} />
          </div>
          <p>
            Cross-source context.
            <br />
            Human-led decisions.
          </p>
        </div>
        <div className="drawer-tabs" role="tablist" aria-label="Customer detail tabs">
          {['Signals', 'Transactions', 'Digital activity', 'Investigation'].map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
              {t}
              {t === 'Investigation' && investigation && <span className="tiny-dot" />}
            </button>
          ))}
        </div>
        <div className="drawer-content" role="tabpanel" aria-label={tab}>
          {tab === 'Signals' && (
            <>
              <h3>What is driving this score?</h3>
              <p className="section-subtitle">Contributions from the existing Gold heuristic</p>
              <div className="factor-list">
                {riskFactors(p).map((f) => (
                  <div className="factor" key={f.name}>
                    <div>
                      <strong>{f.name}</strong>
                      <span>
                        +{f.value.toFixed(1)}
                        <small> / {f.max}</small>
                      </span>
                    </div>
                    <div className="factor-track">
                      <span style={{ width: `${(f.value / f.max) * 100}%` }} />
                    </div>
                    <small>{f.detail}</small>
                  </div>
                ))}
              </div>
              <div className="detail-stats">
                <div>
                  <strong>{number(p.TransactionCount30D)}</strong>
                  <span>Transactions / 30D</span>
                </div>
                <div>
                  <strong>{p.DistinctDeviceCount}</strong>
                  <span>Distinct devices</span>
                </div>
                <div>
                  <strong>{p.FraudAlertCount}</strong>
                  <span>Source fraud alerts</span>
                </div>
              </div>
              <div className="detail-caveat">
                <CircleHelp size={17} />
                <p>
                  Transaction and session windows use independent source-relative dates. Alert and
                  device counts follow the existing Gold formula. This score is an uncalibrated
                  synthetic heuristic.
                </p>
              </div>
              <div className="lineage-meta">
                <span>
                  <Clock3 size={14} /> Gold loaded {dateTime(p.gold_loaded_at)}
                </span>
                <code>Run: {p.pipeline_run_id}</code>
              </div>
            </>
          )}
          {(tab === 'Transactions' || tab === 'Digital activity') && (
            <>
              {detailError ? (
                <div role="alert" className="error-box">
                  Detail query failed: {detailError}
                </div>
              ) : !detail ? (
                <div className="loading-state" role="status">
                  <LoaderCircle className="spin" />
                  Loading customer evidence…
                </div>
              ) : tab === 'Transactions' ? (
                <>
                  <div className="section-title">
                    <h3>Transaction evidence</h3>
                    <span>{detail.transactions.length} retrieved</span>
                  </div>
                  <p className="section-subtitle">
                    Amounts retain source currency. No currency conversion is applied.
                  </p>
                  <div className="table-scroll">
                    <table className="detail-table">
                      <thead>
                        <tr>
                          <th>Transaction / time</th>
                          <th>Amount</th>
                          <th>Channel</th>
                          <th>Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.transactions.map((t) => (
                          <tr key={t.TransactionID}>
                            <td>
                              <strong>{t.TransactionID}</strong>
                              <small>
                                {dateTime(t.TransactionTimestamp)} · {t.TransactionStatus}
                              </small>
                            </td>
                            <td>
                              {t.Currency}{' '}
                              {t.Amount.toLocaleString('en-US', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </td>
                            <td>{t.Channel}</td>
                            <td>{t.RiskScore === null ? '—' : t.RiskScore.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!detail.transactions.length && (
                    <div className="empty-inline">No permitted transaction rows returned.</div>
                  )}
                  {detail.capped && (
                    <p className="bounded-note">
                      Evidence is bounded; these rows are not the complete customer history.
                    </p>
                  )}
                </>
              ) : (
                <>
                  <h3>Source fraud alerts</h3>
                  {detail.alerts.length ? (
                    <div className="alert-list">
                      {detail.alerts.map((a) => (
                        <div key={a.AlertID}>
                          <span className="alert-icon">
                            <Bell size={17} />
                          </span>
                          <div>
                            <strong>{a.alertType.replaceAll('_', ' ')}</strong>
                            <small>
                              {a.AlertID} · {dateTime(a.CreatedTimestamp)}
                            </small>
                            <span>
                              {a.Status} · {a.Severity}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-inline">No permitted source alerts returned.</p>
                  )}
                  <h3 className="spaced-heading">Digital sessions</h3>
                  <div className="table-scroll">
                    <table className="detail-table">
                      <thead>
                        <tr>
                          <th>Session</th>
                          <th>Country</th>
                          <th>MFA</th>
                          <th>Failed attempts</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.sessions.map((s) => (
                          <tr key={s.SessionID}>
                            <td>
                              <strong>{s.AuthenticationMethod}</strong>
                              <small>{dateTime(s.LoginTimestamp)}</small>
                            </td>
                            <td>{s.Country}</td>
                            <td>{s.MfaUsed ? 'Used' : 'Not used'}</td>
                            <td>{s.FailedAttempts}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!detail.sessions.length && (
                    <div className="empty-inline">No permitted sessions returned.</div>
                  )}
                  <p className="bounded-note">
                    Source alert status is read-only and independent of app investigation status. At
                    most 50 rows per evidence type in live mode.
                  </p>
                </>
              )}
            </>
          )}
          {tab === 'Investigation' && (
            <>
              <div className="section-title">
                <h3>{investigation ? 'Investigation workspace' : 'Start an investigation'}</h3>
                {investigation && <span>INV-{investigation.id.slice(0, 8).toUpperCase()}</span>}
              </div>
              <p className="section-subtitle">
                Private to your signed-in identity. Assignment records the intended routing.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void save();
                }}
              >
                <div className="form-row">
                  <label>
                    Status
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value as CaseStatus)}
                    >
                      {statuses.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Assignment label
                    <input
                      value={assignee}
                      onChange={(e) => setAssignee(e.target.value)}
                      maxLength={120}
                      required
                      placeholder="Unassigned"
                    />
                  </label>
                </div>
                <label className="note-label">
                  Investigation note
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    maxLength={2000}
                    placeholder="Capture what you found, why it matters, and the next action…"
                    rows={4}
                  />
                  <small>{note.length}/2,000 · use synthetic information only</small>
                </label>
                {saveError && (
                  <div className="error-box" role="alert">
                    {saveError}
                  </div>
                )}
                <div className="form-actions">
                  {investigation && (
                    <button
                      type="button"
                      className="button secondary"
                      disabled={saving || !note.trim()}
                      onClick={() => void save(true)}
                    >
                      <MessageSquare size={15} /> Add note only
                    </button>
                  )}
                  <button className="button primary" disabled={saving || !assignee.trim()}>
                    {saving ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}{' '}
                    {investigation ? 'Save update' : 'Create investigation'}
                  </button>
                </div>
              </form>
              {investigation && (
                <>
                  <h3 className="spaced-heading">Activity trail</h3>
                  <div className="timeline">
                    {[...investigation.events].reverse().map((event) => (
                      <div className="timeline-entry" key={event.id}>
                        <span className="timeline-dot">
                          <Check size={11} />
                        </span>
                        <div>
                          <strong>
                            {event.eventType === 'created'
                              ? 'Investigation opened'
                              : event.eventType === 'note'
                                ? 'Note added'
                                : `Status set to ${event.status}`}
                          </strong>
                          <small>
                            {dateTime(event.createdAt)} · {event.assignee}
                          </small>
                          {event.note && <p>{event.note}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
        <div className="drawer-footer">
          <span>
            <ShieldCheck size={15} /> Gold data stays read-only
          </span>
          <button className="button primary" onClick={() => setTab('Investigation')}>
            {investigation ? 'Manage investigation' : 'Investigate customer'}
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

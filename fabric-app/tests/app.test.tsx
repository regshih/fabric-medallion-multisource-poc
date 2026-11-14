import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { buildDemo, demoDetail, DEMO_IDENTITY } from '../src/demo';
import type { CaseEvent } from '../src/domain';
import type { Repository } from '../src/repository';

function fixture(): Repository {
  const events: CaseEvent[] = [];
  return {
    mode: 'demo',
    identity: () => DEMO_IDENTITY,
    signIn: vi.fn(),
    signOut: vi.fn(),
    snapshot: async () => buildDemo(),
    profile: async (id) => buildDemo().profiles.find((p) => p.CustomerID === id) ?? null,
    detail: async (p) => demoDetail(p),
    events: async () => [...events],
    append: async (e) => {
      events.push(e);
    },
  };
}
describe('customer investigation workflow', () => {
  it('filters a cohort by customer ID and risk level', async () => {
    const user = userEvent.setup();
    render(<App repository={fixture()} />);
    await screen.findByText('Customers in view');
    await user.click(screen.getByRole('button', { name: 'Customer explorer' }));
    await user.type(screen.getByRole('textbox', { name: 'Search customers' }), 'CUST-000001');
    expect(screen.getAllByText('CUST-000001')).toHaveLength(1);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Risk level' }), 'Low');
    expect(screen.getByText('No customers match these filters.')).toBeInTheDocument();
  });
  it('opens a record, creates a case, saves a note, changes status, and restores it on refresh', async () => {
    const repo = fixture();
    const user = userEvent.setup();
    render(<App repository={repo} />);
    await screen.findByText('Customers in view');
    await user.click(screen.getAllByRole('button', { name: /^Open CUST-/ })[0]);
    const drawer = screen.getByRole('dialog');
    expect(within(drawer).getByText('What is driving this score?')).toBeInTheDocument();
    await user.click(within(drawer).getByRole('button', { name: 'Investigate customer' }));
    await user.clear(within(drawer).getByRole('textbox', { name: 'Assignment label' }));
    await user.type(
      within(drawer).getByRole('textbox', { name: 'Assignment label' }),
      'Fraud operations',
    );
    await user.type(
      within(drawer).getByRole('textbox', { name: /Investigation note/ }),
      'Synthetic device evidence needs review.',
    );
    await user.click(within(drawer).getByRole('button', { name: 'Create investigation' }));
    await screen.findByText('Investigation opened. Your work is saved.');
    await user.selectOptions(within(drawer).getByRole('combobox', { name: 'Status' }), 'Escalated');
    await user.click(within(drawer).getByRole('button', { name: 'Save update' }));
    await screen.findByText('Investigation updated.');
    await user.click(within(drawer).getByRole('button', { name: 'Close customer details' }));
    await user.click(screen.getByRole('button', { name: /^Investigations/ }));
    expect(screen.getByText('Fraud operations', { exact: false })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Refresh' }));
    await waitFor(() => expect(screen.getByText('INV-', { exact: false })).toBeInTheDocument());
    expect(await repo.events()).toHaveLength(2);
  });
  it('shows a failed save without claiming success', async () => {
    const repo = fixture();
    repo.append = async () => {
      throw new Error('Storage is full.');
    };
    const user = userEvent.setup();
    render(<App repository={repo} />);
    await screen.findByText('Customers in view');
    await user.click(screen.getAllByRole('button', { name: /^Open CUST-/ })[0]);
    await user.click(screen.getByRole('button', { name: 'Investigate customer' }));
    await user.click(screen.getByRole('button', { name: 'Create investigation' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Storage is full.');
    expect(screen.queryByText('Investigation opened. Your work is saved.')).not.toBeInTheDocument();
  });
  it('keeps live failures visible and never displays synthetic fixture KPIs', async () => {
    const repo = fixture();
    Object.defineProperty(repo, 'mode', { value: 'live' });
    repo.snapshot = async () => {
      throw new Error('Warehouse access denied.');
    };
    render(<App repository={repo} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Warehouse access denied.');
    expect(screen.queryByText('Customers in view')).not.toBeInTheDocument();
    expect(screen.queryByText('Synthetic demo')).not.toBeInTheDocument();
  });
  it('displays source event amounts in their own currencies', async () => {
    const user = userEvent.setup();
    render(<App repository={fixture()} />);
    await screen.findByText('Customers in view');
    await user.click(screen.getAllByRole('button', { name: /^Open CUST-/ })[0]);
    await user.click(screen.getByRole('tab', { name: 'Transactions' }));
    await screen.findByText('Transaction evidence');
    expect(screen.getAllByText(/^EUR /).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^USD /).length).toBeGreaterThan(0);
  });
  it('flags reconciliation evidence from a different run instead of passing the cohort', async () => {
    const repo = fixture();
    repo.snapshot = async () => {
      const value = buildDemo();
      return {
        ...value,
        quality: value.quality.map((q) => ({ ...q, pipeline_run_id: 'different-run' })),
      };
    };
    render(<App repository={repo} />);
    expect(await screen.findByText('7/7 checks pass · run mismatch')).toBeInTheDocument();
    expect(screen.getByText('Review', { exact: true })).toBeInTheDocument();
    expect(screen.queryByText('PASS', { exact: true })).not.toBeInTheDocument();
  });
});

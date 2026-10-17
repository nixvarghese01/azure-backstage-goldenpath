import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('renders sample orders from the local data endpoint', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, json: async () => [{ id: 'demo-001', customerId: 'cust-001', currency: 'GBP', total: 5 }],
  }));
  render(<App />);
  expect(await screen.findByText(/demo-001/)).toBeDefined();
});

test('shows a recoverable data error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(<App />);
  expect(await screen.findByRole('alert')).toBeDefined();
});

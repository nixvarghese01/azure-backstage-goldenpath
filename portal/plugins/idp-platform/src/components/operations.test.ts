import { freshness, healthDisplay } from './OperationsContent';

describe('healthDisplay', () => {
  it('shows observed health', () => {
    expect(healthDisplay({ health: 'healthy', stale: false })).toEqual({ label: 'Healthy', tone: 'ok' });
    expect(healthDisplay({ health: 'degraded', stale: false }).tone).toBe('warning');
    expect(healthDisplay({ health: 'missing', stale: false }).tone).toBe('error');
  });

  it('never shows unknown or stale data as healthy', () => {
    expect(healthDisplay({ health: 'unknown', stale: true, last_known_health: 'healthy' })).toEqual({
      label: 'Unknown (last seen healthy)',
      tone: 'pending',
    });
    expect(healthDisplay({ health: 'healthy', stale: true })).toEqual({ label: 'Unknown (stale)', tone: 'pending' });
  });
});

describe('freshness', () => {
  const now = new Date('2026-10-21T10:00:30Z');

  it('says how old the observation is', () => {
    expect(freshness({ observed_at: '2026-10-21T10:00:00Z', stale: false }, now)).toBe('observed 30 s ago');
    expect(freshness({ observed_at: '2026-10-21T09:50:00Z', stale: true }, now)).toBe('observed 11 min ago, stale');
  });

  it('says why nothing was observed', () => {
    expect(freshness({ observed_at: null, stale: true, unavailable: 'permission_denied' }, now)).toBe(
      'no observation (permission denied)',
    );
  });
});

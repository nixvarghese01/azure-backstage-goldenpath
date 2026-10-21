import { healthTone, relativeTime, stateTone, summarize, toolkit } from './HomePage';

describe('stateTone', () => {
  it('colors request states', () => {
    expect(stateTone('SUCCEEDED')).toBe('ok');
    expect(stateTone('FAILED')).toBe('error');
    expect(stateTone('AWAITING_APPROVAL')).toBe('warning');
    expect(stateTone('CLEANED_UP')).toBe('aborted');
    expect(stateTone('DEPLOYING')).toBe('running');
  });
});

describe('toolkit', () => {
  it('points at the platform repository', () => {
    const links = Object.fromEntries(toolkit('acme', 'idp').map(t => [t.title, t.url]));
    expect(links).toEqual({
      Docs: '/docs',
      GitHub: 'https://github.com/acme/idp',
      Contributing: 'https://github.com/acme/idp/blob/develop/CONTRIBUTING.md',
      'Plugins Directory': 'https://backstage.io/plugins',
      'Submit New Issue': 'https://github.com/acme/idp/issues/new/choose',
    });
  });
});

describe('healthTone', () => {
  it('never shows unknown as healthy', () => {
    expect(healthTone('healthy')).toBe('ok');
    expect(healthTone('degraded')).toBe('warning');
    expect(healthTone('down')).toBe('error');
    expect(healthTone('unknown')).toBe('pending');
    expect(healthTone(undefined)).toBe('pending');
  });
});

describe('summarize', () => {
  const now = new Date('2026-10-22T12:00:00Z');
  it('counts the last 7 days and the success rate of finished requests', () => {
    const requests = [
      { state: 'SUCCEEDED', created_at: '2026-10-21T10:00:00Z' },
      { state: 'FAILED', created_at: '2026-10-20T10:00:00Z' },
      { state: 'SUCCEEDED', created_at: '2026-10-01T10:00:00Z' },
      { state: 'DEPLOYING', created_at: '2026-10-22T11:00:00Z' },
    ];
    expect(summarize(requests, now)).toEqual({ lastWeek: 3, successRate: 67 });
  });
  it('has no rate before anything finished', () => {
    expect(summarize([{ state: 'DEPLOYING', created_at: '2026-10-22T11:00:00Z' }], now).successRate).toBeNull();
  });
});

describe('relativeTime', () => {
  const now = new Date('2026-10-22T12:00:00Z');
  it('reads like a person would say it', () => {
    expect(relativeTime('2026-10-22T11:59:40Z', now)).toBe('just now');
    expect(relativeTime('2026-10-22T11:55:00Z', now)).toBe('5 min ago');
    expect(relativeTime('2026-10-22T09:00:00Z', now)).toBe('3 h ago');
    expect(relativeTime('2026-10-20T12:00:00Z', now)).toBe('2 d ago');
  });
});

import { stateTone, toolkit } from './HomePage';

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

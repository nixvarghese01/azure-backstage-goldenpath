import { pinWorkflowRefs } from './workflowRefs';

describe('pinWorkflowRefs', () => {
  const wf = [
    'jobs:',
    '  plan:',
    '    uses: nixvarghese01/azure-backstage-goldenpath/.github/workflows/reusable-terraform.yml@main',
    '  other:',
    '    uses: actions/checkout@v4',
  ].join('\n');

  it('points platform reusable workflows at the platform ref, nothing else', () => {
    const out = pinWorkflowRefs(wf, 'develop');
    expect(out).toContain('reusable-terraform.yml@develop');
    expect(out).toContain('actions/checkout@v4');
  });

  it('rejects refs GitHub would not accept', () => {
    expect(() => pinWorkflowRefs(wf, 'main; rm -rf /')).toThrow('invalid platform ref');
  });
});

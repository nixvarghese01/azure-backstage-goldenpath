import { unregisteredWorkflows } from './repositoryCreated';

describe('unregisteredWorkflows', () => {
  it('lists workflow files GitHub has not registered', () => {
    expect(unregisteredWorkflows(
      ['.github/workflows/terraform-plan.yml', '.github/workflows/terraform-validate.yml', '.github/workflows/README.md'],
      ['.github/workflows/terraform-plan.yml'],
    )).toEqual(['.github/workflows/terraform-validate.yml']);
  });

  it('is empty once everything is registered', () => {
    expect(unregisteredWorkflows(['.github/workflows/a.yaml'], ['.github/workflows/a.yaml'])).toEqual([]);
  });
});

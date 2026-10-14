import type { FieldValidation } from '@rjsf/utils';
import type { InfrastructureSelection } from '@internal/plugin-idp-platform-common';
import { validateAvailability } from './AvailabilityPicker';
import { validateInfrastructure } from './AzureResourcePicker';
import { defaultEndpointHost, validateEndpointHost } from './EndpointHostPicker';

function collector() {
  const errors: string[] = [];
  const validation = { addError: (e: string) => errors.push(e), __errors: errors } as unknown as FieldValidation;
  return { validation, errors };
}

const good: InfrastructureSelection = {
  tenantId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  managementGroup: 'xycorp-corp',
  region: 'uksouth',
  subscription: { mode: 'existing', id: 'sub', name: 'sub-idp-dev' },
  resourceGroup: { mode: 'existing', name: 'rg-idp-apps-dev' },
  aksCluster: { mode: 'existing', name: 'aks-idp-shared-dev', resourceGroup: 'rg-idp-platform-dev' },
  containerRegistry: { mode: 'existing', name: 'acridpdev', resourceGroup: 'rg-idp-platform-dev' },
  namespace: { mode: 'new', name: 'orders-api' },
  runtimeCapability: { type: 'storage', mode: 'existing', name: 'stidpshareddev' },
};

describe('validateInfrastructure', () => {
  it('accepts the golden-path selection', () => {
    const { validation, errors } = collector();
    validateInfrastructure(good, validation);
    expect(errors).toEqual([]);
  });

  it('requires the tenant and landing zone management group', () => {
    const { validation, errors } = collector();
    validateInfrastructure({ ...good, tenantId: undefined, managementGroup: undefined }, validation);
    expect(errors).toEqual(['Tenant: select one.', 'Management group: select the landing zone.']);
  });

  it('requires names and rejects bad resource group and namespace names', () => {
    const { validation, errors } = collector();
    validateInfrastructure(
      { ...good, resourceGroup: { mode: 'new', name: 'my-rg' }, namespace: { mode: 'new', name: 'kube-system' },
        aksCluster: { mode: 'existing' } },
      validation,
    );
    expect(errors.join('\n')).toMatch(/rg-<name>/);
    expect(errors.join('\n')).toMatch(/kube-/);
    expect(errors.join('\n')).toMatch(/AKS cluster/);
  });

  it('needs a region', () => {
    const { validation, errors } = collector();
    validateInfrastructure({ ...good, region: '' }, validation);
    expect(errors.join('\n')).toMatch(/Region/);
  });
});

describe('validateAvailability', () => {
  const ctx = { formData: { environment: 'dev' } };

  it('needs no justification for the dev default', () => {
    const { validation, errors } = collector();
    validateAvailability({ tier: 'standard' }, validation, ctx);
    expect(errors).toEqual([]);
  });

  it('requires a reason and a real justification for HA in dev', () => {
    const { validation, errors } = collector();
    validateAvailability({ tier: 'ha', justification: 'n/a' }, validation, ctx);
    expect(errors).toHaveLength(2);
  });

  it('accepts a justified HA request', () => {
    const { validation, errors } = collector();
    validateAvailability(
      { tier: 'ha', reason: 'customer-facing', justification: 'Public checkout API; outages block orders.' },
      validation,
      ctx,
    );
    expect(errors).toEqual([]);
  });
});

describe('endpoint host', () => {
  it('defaults to <name>.<gateway domain of the selected cluster>', () => {
    expect(defaultEndpointHost({ name: 'orders-api', infrastructure: { baseDomain: 'dev.xycorp.local' } }))
      .toBe('orders-api.dev.xycorp.local');
    expect(defaultEndpointHost({ name: 'orders-api' })).toBe('');
  });

  it('accepts empty (server default) and valid hosts, rejects malformed ones', () => {
    for (const ok of ['', 'orders-api.dev.xycorp.local', 'api.example.com']) {
      const { validation, errors } = collector();
      validateEndpointHost(ok, validation);
      expect(errors).toEqual([]);
    }
    const { validation, errors } = collector();
    validateEndpointHost('Not A Host', validation);
    expect(errors).toHaveLength(1);
  });
});

import { TestApiProvider } from '@backstage/test-utils';
import { render, screen, waitFor } from '@testing-library/react';
import { type ComponentType, createElement as h, useState } from 'react';
import { type IdpApi, idpApiRef } from '../api';
import { AvailabilityPicker } from './AvailabilityPicker';
import { AzureResourcePicker } from './AzureResourcePicker';

// The scaffolder form starts an object field as {} rather than undefined. Both pickers used
// `formData ?? defaults`, so {} skipped the defaults and the resource picker crashed with
// "Cannot read properties of undefined (reading 'mode')". (createElement, not JSX: the repo's classic JSX
// transform needs a React default import, which lint rejects in new files.)
const api = {
  tenants: async () => [{ id: 't1', name: 'Tenant' }],
  managementGroups: async () => [{ id: 'mg1', name: 'Corp', tenant_id: 't1', path: ['Tenant Root Group', 'Corp'], depth: 1 }],
  subscriptions: async () => [{ id: 's1', name: 'sub-dev' }],
  list: async (_s: string, kind: string) =>
    kind === 'resource-groups' ? [{ id: 'rg1', name: 'rg-apps-dev', location: 'swedencentral' }] : [],
  dataResources: async () => [],
  capabilities: async () => ({ create_new: {} }),
} as unknown as IdpApi;

const props = (formData: unknown, onChange: (v: unknown) => void) => ({
  formData, onChange, rawErrors: [], schema: {}, uiSchema: {}, idSchema: { $id: 'f' }, required: true,
  formContext: { formData: { name: 'orders-api', environment: 'dev', stack: 'nestjs' } },
}) as any;

/** Feeds each change back as formData, as the scaffolder form does. */
const Form = ({ Field, onChange }: { Field: ComponentType<any>; onChange: jest.Mock }) => {
  const [data, setData] = useState<unknown>({});
  return h(Field, props(data, (v: unknown) => { onChange(v); setData(v); }));
};

describe('pickers with the form\'s initial {}', () => {
  it('AzureResourcePicker renders and prefills the defaults', async () => {
    const onChange = jest.fn();
    render(h(TestApiProvider, { apis: [[idpApiRef, api]] as const, children: h(Form, { Field: AzureResourcePicker, onChange }) }));
    // Prefill runs as each approved list arrives; wait for the subscription level.
    await waitFor(() => expect(onChange.mock.calls.at(-1)?.[0].subscription).toMatchObject({ mode: 'existing', id: 's1' }));
    expect(onChange.mock.calls.at(-1)[0].namespace).toEqual({ mode: 'new', name: 'orders-api' });
  });

  it('AvailabilityPicker sets the environment default tier', async () => {
    const onChange = jest.fn();
    render(h(Form, { Field: AvailabilityPicker, onChange }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ tier: 'standard' }));
    expect(screen.getAllByText(/Availability/).length).toBeGreaterThan(0);
  });
});

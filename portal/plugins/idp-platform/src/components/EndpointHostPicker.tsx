import type { FieldExtensionComponentProps } from '@backstage/plugin-scaffolder-react';
import type { FieldValidation } from '@rjsf/utils';
import React, { useEffect, useState } from 'react';
import { CUSTOM, DefaultOrCustomSelect } from './DefaultOrCustomSelect';

const DEFAULT = '__default__';
const HOST = /^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)+$/;

/** <name>.<gateway domain of the selected cluster>, or '' while the cluster's domain is unknown. */
export function defaultEndpointHost(formData: Record<string, any> | undefined): string {
  const name: string = formData?.name ?? '';
  const domain: string | undefined = formData?.infrastructure?.baseDomain;
  return name && domain ? `${name}.${domain}` : '';
}

/**
 * Endpoint host dropdown: the platform default (<name>.<gateway domain>) or a custom host.
 * An empty value also means "platform default"; the server derives it during validation.
 */
export const EndpointHostPicker = ({ formData, onChange, formContext }: FieldExtensionComponentProps<string>) => {
  const fallback = defaultEndpointHost((formContext as any)?.formData);
  const [custom, setCustom] = useState(!!formData && formData !== fallback);

  // Track the default while it's selected (the name or cluster may change on an earlier step).
  useEffect(() => {
    if (!custom && (formData ?? '') !== fallback) onChange(fallback);
  }, [custom, fallback]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DefaultOrCustomSelect
      label="Endpoint host"
      options={[{
        value: DEFAULT,
        label: fallback ? `${fallback} (default)` : 'Platform default: <name>.<cluster gateway domain>',
      }]}
      selected={custom ? CUSTOM : DEFAULT}
      onSelect={v => {
        const isCustom = v === CUSTOM;
        setCustom(isCustom);
        onChange(isCustom ? formData || fallback : fallback);
      }}
      customLabel="Custom…"
      customValue={formData}
      onCustomChange={host => onChange(host.toLowerCase())}
      customFieldLabel="Host name"
      customPlaceholder={fallback || 'orders-api.dev.xycorp.local'}
      customHelp="Outside the gateway domain you add the DNS record and TLS certificate yourself."
    />
  );
};

export const validateEndpointHost = (value: string, validation: FieldValidation) => {
  if (value && (!HOST.test(value) || value.length > 253)) {
    validation.addError('Enter a host name such as orders-api.dev.xycorp.local.');
  }
};

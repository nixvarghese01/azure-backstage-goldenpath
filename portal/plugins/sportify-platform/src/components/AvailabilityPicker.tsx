import type { FieldExtensionComponentProps } from '@backstage/plugin-scaffolder-react';
import type { FieldValidation } from '@rjsf/utils';
import type { AvailabilitySelection } from '@internal/plugin-sportify-platform-common';
import { Box, FormControl, FormHelperText, MenuItem, TextField, Typography } from '@material-ui/core';
import React, { useEffect } from 'react';

// Mirrors policies/allowlist.yaml (ha.*). The server re-validates; this is only for a good UX.
const REASONS: Record<string, string> = {
  'customer-facing': 'Customer-facing',
  'contractual-sla': 'Contractual SLA',
  'revenue-or-safety-critical': 'Revenue- or safety-critical',
  'dependency-of-critical-service': 'Dependency of a critical service',
  'testing-ha-behaviour': 'Testing HA behaviour',
  other: 'Other',
};
const SLOS = ['99.5', '99.9', '99.95'];
const HA_DEFAULT: Record<string, boolean> = { dev: false, test: false, prod: true };
const MIN_JUSTIFICATION = 30;
const PLACEHOLDERS = new Set(['test', 'testing', 'n/a', 'na', 'none', 'asdf', 'tbd', 'todo', '-', '.']);

function deviates(value: AvailabilitySelection | undefined, environment: string): boolean {
  return (value?.tier === 'ha') !== (HA_DEFAULT[environment] ?? false);
}

/** ADR-0004: availability dropdown preselected with the environment default; deviating needs a justification. */
export const AvailabilityPicker = (props: FieldExtensionComponentProps<AvailabilitySelection>) => {
  const { formData, onChange, formContext } = props;
  const environment: string = (formContext as any)?.formData?.environment ?? 'dev';
  const defaultTier = HA_DEFAULT[environment] ? 'ha' : 'standard';
  const value: AvailabilitySelection = formData ?? { tier: defaultTier };
  const set = (patch: Partial<AvailabilitySelection>) => onChange({ ...value, ...patch });
  const needsJustification = deviates(value, environment);

  useEffect(() => {
    if (!formData) onChange({ tier: defaultTier });
  }, [formData, defaultTier]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <FormControl fullWidth>
      <TextField select fullWidth size="small" label="Availability" value={value.tier}
        onChange={e => set({ tier: e.target.value as 'standard' | 'ha' })}>
        <MenuItem value="standard">
          Standard - one pod, minimum resources{defaultTier === 'standard' ? ' (default)' : ''}
        </MenuItem>
        <MenuItem value="ha">
          High availability - 2+ pods across zones, autoscaling{defaultTier === 'ha' ? ' (default)' : ''}
        </MenuItem>
      </TextField>
      <FormHelperText>
        HA adds a disruption budget and zone-redundant storage for new storage. It increases cost and needs approval.
      </FormHelperText>
      {needsJustification && (
        <Box mt={2} display="flex" flexDirection="column" gridGap={16}>
          <Typography variant="body2">
            This differs from the {environment} default, so the approver needs to know why.
          </Typography>
          <TextField select label="Reason" required value={value.reason ?? ''} onChange={e => set({ reason: e.target.value })}>
            {Object.entries(REASONS).map(([k, label]) => (
              <MenuItem key={k} value={k}>{label}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Justification"
            required
            multiline
            minRows={3}
            inputProps={{ maxLength: 500 }}
            helperText={`At least ${MIN_JUSTIFICATION} characters.`}
            value={value.justification ?? ''}
            onChange={e => set({ justification: e.target.value })}
          />
          {value.tier === 'ha' && (
            <TextField select label="Target availability (SLO)" value={value.sloTarget ?? ''} onChange={e => set({ sloTarget: e.target.value })}>
              {SLOS.map(s => (
                <MenuItem key={s} value={s}>{s} %</MenuItem>
              ))}
            </TextField>
          )}
        </Box>
      )}
    </FormControl>
  );
};

export const validateAvailability = (
  value: AvailabilitySelection,
  validation: FieldValidation,
  context: { formData?: Record<string, unknown> } | any,
) => {
  const environment = (context?.formData?.environment as string) ?? 'dev';
  if (!deviates(value, environment)) return;
  if (!value?.reason) validation.addError('Choose a reason for deviating from the default availability.');
  const text = (value?.justification ?? '').trim();
  if (text.length < MIN_JUSTIFICATION || PLACEHOLDERS.has(text.toLowerCase())) {
    validation.addError(`Explain why in at least ${MIN_JUSTIFICATION} characters.`);
  }
};

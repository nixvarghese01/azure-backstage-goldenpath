import type { FieldExtensionComponentProps, FieldValidation } from '@backstage/plugin-scaffolder-react';
import type { AvailabilitySelection } from '@internal/plugin-sportify-platform-common';
import {
  Box,
  FormControl,
  FormControlLabel,
  FormLabel,
  MenuItem,
  Radio,
  RadioGroup,
  TextField,
  Typography,
} from '@material-ui/core';
import { Alert } from '@material-ui/lab';
import React from 'react';

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

/** ADR-0004: "Do you need high availability?" with a justification when deviating from the default. */
export const AvailabilityPicker = (props: FieldExtensionComponentProps<AvailabilitySelection>) => {
  const { formData, onChange, formContext } = props;
  const environment: string = (formContext as any)?.formData?.environment ?? 'dev';
  const value: AvailabilitySelection = formData ?? { tier: HA_DEFAULT[environment] ? 'ha' : 'standard' };
  const set = (patch: Partial<AvailabilitySelection>) => onChange({ ...value, ...patch });
  const needsJustification = deviates(value, environment);

  return (
    <FormControl component="fieldset" fullWidth>
      <FormLabel component="legend">Do you need high availability?</FormLabel>
      <RadioGroup row value={value.tier} onChange={e => set({ tier: e.target.value as 'standard' | 'ha' })}>
        <FormControlLabel value="ha" control={<Radio />} label="Yes" />
        <FormControlLabel value="standard" control={<Radio />} label={`No${HA_DEFAULT[environment] ? '' : ' (default)'}`} />
      </RadioGroup>
      <Alert severity="info">
        HA runs at least 2 replicas across availability zones, with a disruption budget and autoscaling, and uses
        zone-redundant storage when creating new storage. It increases cost and needs approval.
      </Alert>
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

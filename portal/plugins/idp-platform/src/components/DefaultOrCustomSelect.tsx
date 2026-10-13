import { Box, FormHelperText, MenuItem, TextField } from '@material-ui/core';
import React from 'react';

export const CUSTOM = '__custom__';

export interface Option {
  value: string;
  label: string;
  disabled?: boolean;
}

interface Props {
  label: string;
  options: Option[];
  /** The selected option value, or CUSTOM. */
  selected: string;
  onSelect: (value: string) => void;
  /** Label of the "enter your own value" entry; omit to offer no custom entry. */
  customLabel?: string;
  /** Why the custom entry is unavailable (shown and disables it). */
  customDisabledReason?: string;
  customValue?: string;
  onCustomChange?: (value: string) => void;
  customFieldLabel?: string;
  customPlaceholder?: string;
  customHelp?: string;
  helperText?: string;
}

/**
 * A dropdown preselected with the platform default. Picking the custom entry reveals a text field,
 * so a request needs typing only when it deviates from the standard.
 */
export const DefaultOrCustomSelect = ({
  label, options, selected, onSelect, customLabel, customDisabledReason, customValue, onCustomChange,
  customFieldLabel, customPlaceholder, customHelp, helperText,
}: Props) => (
  <Box mb={2}>
    <TextField select fullWidth size="small" label={label} value={selected} onChange={e => onSelect(e.target.value)}>
      {options.map(o => (
        <MenuItem key={o.value} value={o.value} disabled={o.disabled}>{o.label}</MenuItem>
      ))}
      {customLabel && (
        <MenuItem value={CUSTOM} disabled={!!customDisabledReason}>{customLabel}</MenuItem>
      )}
    </TextField>
    {customDisabledReason && <FormHelperText>{customLabel} unavailable: {customDisabledReason}</FormHelperText>}
    {helperText && <FormHelperText>{helperText}</FormHelperText>}
    {selected === CUSTOM && onCustomChange && (
      <Box mt={1}>
        <TextField
          fullWidth
          size="small"
          label={customFieldLabel ?? 'Name'}
          placeholder={customPlaceholder}
          helperText={customHelp}
          value={customValue ?? ''}
          onChange={e => onCustomChange(e.target.value.trim())}
        />
      </Box>
    )}
  </Box>
);

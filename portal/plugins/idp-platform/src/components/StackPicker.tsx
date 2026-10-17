import { Progress } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import type { FieldExtensionComponentProps } from '@backstage/plugin-scaffolder-react';
import { FormHelperText, MenuItem, TextField } from '@material-ui/core';
import React, { useEffect } from 'react';
import useAsync from 'react-use/esm/useAsync';
import { idpApiRef } from '../api';

/** Dropdown of the platform's stacks, preselected with the default; stacks not enabled yet are "coming soon". */
export const StackPicker = ({ formData, onChange, schema, rawErrors, required }: FieldExtensionComponentProps<string>) => {
  const api = useApi(idpApiRef);
  const { value: stacks, loading, error } = useAsync(() => api.stacks(), [api]);
  const fallback = (schema.default as string | undefined) ?? 'nestjs';

  useEffect(() => {
    if (!formData) onChange(fallback);
  }, [formData, fallback]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <Progress />;
  return (
    <>
      <TextField
        select
        fullWidth
        size="small"
        required={required}
        error={!!rawErrors?.length || !!error}
        label={schema.title ?? 'Stack'}
        value={formData ?? fallback}
        onChange={e => onChange(e.target.value)}
      >
        {(stacks ?? []).map(s => (
          <MenuItem key={s.id} value={s.id} disabled={!s.enabled}>
            {s.name}{s.id === fallback ? ' (default)' : ''}{s.enabled ? '' : ' (coming soon)'}
          </MenuItem>
        ))}
      </TextField>
      {error && <FormHelperText error>Couldn't load stacks: {error.message}</FormHelperText>}
      {schema.description && <FormHelperText>{schema.description}</FormHelperText>}
    </>
  );
};

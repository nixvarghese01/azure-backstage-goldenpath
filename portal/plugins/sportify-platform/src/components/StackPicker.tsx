import { Progress } from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import type { FieldExtensionComponentProps } from '@backstage/plugin-scaffolder-react';
import { FormControl, FormControlLabel, FormHelperText, FormLabel, Radio, RadioGroup } from '@material-ui/core';
import React from 'react';
import useAsync from 'react-use/esm/useAsync';
import { sportifyApiRef } from '../api';

/** Lists the platform's stacks; stacks that aren't enabled yet are shown but disabled ("coming soon"). */
export const StackPicker = ({ formData, onChange, schema, rawErrors, required }: FieldExtensionComponentProps<string>) => {
  const api = useApi(sportifyApiRef);
  const { value: stacks, loading, error } = useAsync(() => api.stacks(), [api]);
  if (loading) return <Progress />;
  return (
    <FormControl required={required} error={!!rawErrors?.length || !!error}>
      <FormLabel>{schema.title ?? 'Stack'}</FormLabel>
      <RadioGroup value={formData ?? ''} onChange={e => onChange(e.target.value)}>
        {(stacks ?? []).map(s => (
          <FormControlLabel
            key={s.id}
            value={s.id}
            control={<Radio />}
            disabled={!s.enabled}
            label={s.enabled ? s.name : `${s.name} (coming soon)`}
          />
        ))}
      </RadioGroup>
      {error && <FormHelperText>Couldn't load stacks: {error.message}</FormHelperText>}
      {schema.description && <FormHelperText>{schema.description}</FormHelperText>}
    </FormControl>
  );
};

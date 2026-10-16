import { githubAuthApiRef, useApi } from '@backstage/core-plugin-api';
import { type FieldExtensionComponentProps, useTemplateSecrets } from '@backstage/plugin-scaffolder-react';
import type { FieldValidation } from '@rjsf/utils';
import { Button, FormHelperText, Typography } from '@material-ui/core';
import React, { useCallback, useEffect, useState } from 'react';

/** The template's GitHub steps run with this secret: the signed-in user's GitHub token. */
export const GITHUB_TOKEN_SECRET = 'USER_OAUTH_TOKEN';

/**
 * Asks for the signed-in user's GitHub token and keeps it as a template secret (never in the form's
 * values). Needed when repositories land in a personal account: a GitHub App installation can create
 * repositories only in organizations, so the repository is created as the user. Value: "granted".
 */
export const GithubAccess = ({ onChange, formData }: FieldExtensionComponentProps<string>) => {
  const github = useApi(githubAuthApiRef);
  const { setSecrets } = useTemplateSecrets();
  const [error, setError] = useState<string>();

  const request = useCallback(async (instantPopup: boolean) => {
    setError(undefined);
    try {
      // GitHub App user tokens ignore OAuth scopes; the app's permissions apply.
      const token = await github.getAccessToken(['repo', 'workflow'], { instantPopup });
      if (!token) throw new Error('GitHub returned no token');
      setSecrets({ [GITHUB_TOKEN_SECRET]: token });
      onChange('granted');
    } catch (e) {
      setError((e as Error).message);
      onChange(undefined);
    }
  }, [github, setSecrets, onChange]);

  useEffect(() => {
    request(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (formData === 'granted') {
    return <Typography variant="body2">GitHub access granted: the repository is created with your account.</Typography>;
  }
  return (
    <>
      <Button variant="outlined" color="primary" onClick={() => request(true)}>Grant GitHub access</Button>
      <FormHelperText error={!!error}>
        {error ?? 'The repository is created with your GitHub account.'}
      </FormHelperText>
    </>
  );
};

export const validateGithubAccess = (value: string | undefined, validation: FieldValidation) => {
  if (value !== 'granted') validation.addError('Grant GitHub access to create the repository.');
};

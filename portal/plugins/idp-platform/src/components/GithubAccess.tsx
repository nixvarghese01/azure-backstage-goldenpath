import { configApiRef, githubAuthApiRef, useApi } from '@backstage/core-plugin-api';
import { type FieldExtensionComponentProps, useTemplateSecrets } from '@backstage/plugin-scaffolder-react';
import type { FieldValidation } from '@rjsf/utils';
import { Button, FormHelperText, Typography } from '@material-ui/core';
import React, { useCallback, useEffect, useState } from 'react';

/** The template's GitHub steps run with this secret: the signed-in user's GitHub token. */
export const GITHUB_TOKEN_SECRET = 'USER_OAUTH_TOKEN';

/**
 * idp.githubOwnerType "user" (a personal account): asks for the signed-in user's GitHub token and keeps it
 * as a template secret (never in the form's values), because a GitHub App installation can create
 * repositories only in organizations. Value "granted". "organization": the platform's GitHub App creates
 * the repository; value "not-needed" and nothing to do.
 */
export const GithubAccess = ({ onChange, formData }: FieldExtensionComponentProps<string>) => {
  const personal = useApi(configApiRef).getOptionalString('idp.githubOwnerType') === 'user';
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
    if (personal) request(false);
    else if (formData !== 'not-needed') onChange('not-needed');
  }, [personal]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!personal) {
    return <Typography variant="body2">The platform's GitHub App creates the repository in the organization.</Typography>;
  }
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
  if (value !== 'granted' && value !== 'not-needed') validation.addError('Grant GitHub access to create the repository.');
};

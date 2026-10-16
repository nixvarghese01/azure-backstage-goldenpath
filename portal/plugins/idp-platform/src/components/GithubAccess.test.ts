import { configApiRef, githubAuthApiRef } from '@backstage/core-plugin-api';
import { TestApiProvider, mockApis } from '@backstage/test-utils';
import { SecretsContextProvider } from '@backstage/plugin-scaffolder-react';
import { render, waitFor } from '@testing-library/react';
import { createElement as h } from 'react';
import { GithubAccess } from './GithubAccess';

const renderField = (ownerType: string, getAccessToken: jest.Mock) => {
  const onChange = jest.fn();
  const config = mockApis.config({ data: { idp: { githubOwnerType: ownerType } } });
  render(h(TestApiProvider, {
    apis: [[configApiRef, config], [githubAuthApiRef, { getAccessToken }]] as const,
    children: h(SecretsContextProvider, null, h(GithubAccess, { onChange, formData: undefined } as any)),
  }));
  return onChange;
};

describe('GithubAccess', () => {
  it('personal account: fetches the user token and marks access granted', async () => {
    const getAccessToken = jest.fn().mockResolvedValue('gho_token');
    const onChange = renderField('user', getAccessToken);
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('granted'));
  });

  it('organization: no user token is requested', async () => {
    const getAccessToken = jest.fn();
    const onChange = renderField('organization', getAccessToken);
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('not-needed'));
    expect(getAccessToken).not.toHaveBeenCalled();
  });
});

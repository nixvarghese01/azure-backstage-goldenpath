export interface Config {
  idp?: {
    /**
     * Who owns idp.githubOrg. "user" (a personal account): the template creates the repository with the
     * signed-in user's GitHub token, because a GitHub App installation can create repositories only in
     * organizations. "organization" (default): the platform's GitHub App creates it.
     * Declared here, in the frontend plugin: the app serves only frontend packages' frontend-visible config.
     * @visibility frontend
     */
    githubOwnerType?: 'user' | 'organization';
  };
}

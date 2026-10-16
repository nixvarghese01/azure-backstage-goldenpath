export interface Config {
  idp: {
    /** GitHub organisation that holds generated repositories and the platform repository. */
    githubOrg: string;
    /**
     * Who owns githubOrg. "organization": the platform's GitHub App creates repositories (installation
     * token). "user": a personal account, where an App installation can't create repositories, so the
     * template uses the signed-in user's GitHub token. Default "organization". The frontend reads it
     * through the idp-platform plugin's schema (frontend visibility must be declared there).
     */
    githubOwnerType?: 'user' | 'organization';
    /**
     * Ref of the platform repository that generated repositories use: its catalog templates and
     * reusable workflows (`uses: ...@<ref>`). platform-release sets the branch it deploys from.
     * Default "main".
     */
    platformRef?: string;
    /** GitHub App ID of the orchestrator (App #2), used as the custom deployment protection rule. */
    orchestratorGithubAppId: number;
    discovery: { baseUrl: string };
    orchestrator: { baseUrl: string };
    auth: {
      /** "entra" in Azure (Workload Identity tokens), "static" for local development only. */
      mode: 'entra' | 'static';
      discoveryScope?: string;
      orchestratorScope?: string;
      /** @visibility secret */
      devToken?: string;
    };
    /** Maximum time the submit action waits for validation / platform provisioning. */
    submitTimeoutMinutes?: number;
    stacks?: Array<{ id: string; name: string; enabled: boolean }>;
  };
}

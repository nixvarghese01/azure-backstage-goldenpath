export interface Config {
  idp: {
    /** GitHub organisation that holds generated repositories and the platform repository. */
    githubOrg: string;
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

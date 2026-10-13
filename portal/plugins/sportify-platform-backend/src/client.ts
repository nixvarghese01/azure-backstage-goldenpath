import { DefaultAzureCredential } from '@azure/identity';
import type { Config } from '@backstage/config';
import { ResponseError } from '@backstage/errors';

export interface UserContext {
  userRef: string;
  groupRefs: string[];
}

/**
 * Thin HTTP client for the Python platform services. Authenticates as the Backstage workload
 * (Entra token, or the static dev token locally) and forwards the *verified* user context.
 * No business logic lives here.
 */
export class PlatformClient {
  private readonly credential?: DefaultAzureCredential;

  private constructor(
    private readonly discoveryUrl: string,
    private readonly orchestratorUrl: string,
    private readonly mode: 'entra' | 'static',
    private readonly scopes: { discovery?: string; orchestrator?: string },
    private readonly devToken?: string,
  ) {
    if (mode === 'entra') this.credential = new DefaultAzureCredential();
  }

  static fromConfig(config: Config): PlatformClient {
    const mode = config.getString('sportify.auth.mode') as 'entra' | 'static';
    return new PlatformClient(
      config.getString('sportify.discovery.baseUrl').replace(/\/$/, ''),
      config.getString('sportify.orchestrator.baseUrl').replace(/\/$/, ''),
      mode,
      {
        discovery: config.getOptionalString('sportify.auth.discoveryScope'),
        orchestrator: config.getOptionalString('sportify.auth.orchestratorScope'),
      },
      config.getOptionalString('sportify.auth.devToken'),
    );
  }

  private async token(service: 'discovery' | 'orchestrator'): Promise<string> {
    if (this.mode === 'static') {
      if (!this.devToken) throw new Error('sportify.auth.devToken is required in static mode');
      return this.devToken;
    }
    const scope = this.scopes[service];
    if (!scope) throw new Error(`sportify.auth.${service}Scope is not configured`);
    const token = await this.credential!.getToken(scope);
    return token.token;
  }

  private async call<T>(
    service: 'discovery' | 'orchestrator',
    method: string,
    path: string,
    opts: { user?: UserContext; body?: unknown; query?: Record<string, string | undefined> } = {},
  ): Promise<T> {
    const base = service === 'discovery' ? this.discoveryUrl : this.orchestratorUrl;
    const url = new URL(`${base}${path}`);
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== undefined && v !== '') url.searchParams.set(k, v);
    }
    const headers: Record<string, string> = {
      Authorization: `Bearer ${await this.token(service)}`,
      'Content-Type': 'application/json',
    };
    if (opts.user) {
      headers['X-Sportify-User'] = opts.user.userRef;
      headers['X-Sportify-Groups'] = opts.user.groupRefs.join(',');
    }
    const res = await fetch(url, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: AbortSignal.timeout(service === 'discovery' ? 10_000 : 15_000),
    });
    if (!res.ok) throw await ResponseError.fromResponse(res);
    return (await res.json()) as T;
  }

  discovery<T>(path: string, query?: Record<string, string | undefined>): Promise<T> {
    return this.call<T>('discovery', 'GET', path, { query });
  }

  orchestrator<T>(method: string, path: string, opts?: { user?: UserContext; body?: unknown;
    query?: Record<string, string | undefined> }): Promise<T> {
    return this.call<T>('orchestrator', method, path, opts);
  }
}

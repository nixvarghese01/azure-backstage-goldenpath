import { plainToInstance, Transform } from 'class-transformer';
import { IsIn, IsInt, IsOptional, IsString, Matches, Max, Min, validateSync } from 'class-validator';

/**
 * Environment configuration, validated at startup. Only non-secret settings live here:
 * Azure access uses Workload Identity (DefaultAzureCredential), never keys or connection strings.
 */
export class AppConfig {
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(65535)
  PORT = 3000;

  @IsOptional()
  @IsIn(['development', 'test', 'production'])
  NODE_ENV = 'production';

  /** Storage account name; when unset the service uses an in-memory store (local dev and tests). */
  @Transform(({ value }: { value: unknown }) => (value === '' ? undefined : value))
  @IsOptional()
  @Matches(/^[a-z0-9]{3,24}$/)
  AZURE_STORAGE_ACCOUNT?: string;

  @IsOptional()
  @IsString()
  AZURE_STORAGE_CONTAINER = 'app-data';
}

export function validateConfig(raw: Record<string, unknown>): AppConfig {
  const config = plainToInstance(AppConfig, raw, { enableImplicitConversion: true });
  const errors = validateSync(config, { skipMissingProperties: false });
  if (errors.length > 0) {
    throw new Error(`Invalid configuration: ${errors.map((e) => e.property).join(', ')}`);
  }
  return config;
}

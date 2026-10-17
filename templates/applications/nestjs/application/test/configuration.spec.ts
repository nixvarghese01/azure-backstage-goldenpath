import 'reflect-metadata';
import { validateConfig } from '../src/config/configuration';

describe('application configuration', () => {
  it('accepts an empty storage account from local Compose as an unset capability', () => {
    expect(validateConfig({ AZURE_STORAGE_ACCOUNT: '' }).AZURE_STORAGE_ACCOUNT).toBeUndefined();
  });

  it('retains a valid deployed storage account', () => {
    expect(validateConfig({ AZURE_STORAGE_ACCOUNT: 'stordersapidev' }).AZURE_STORAGE_ACCOUNT)
      .toBe('stordersapidev');
  });

  it('rejects a malformed nonempty storage account', () => {
    expect(() => validateConfig({ AZURE_STORAGE_ACCOUNT: 'invalid-account' }))
      .toThrow('Invalid configuration: AZURE_STORAGE_ACCOUNT');
  });
});

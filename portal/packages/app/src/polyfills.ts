// crypto.randomUUID exists only in secure contexts (https or localhost). The dev platform serves the
// portal over plain http (no certificate on the Azure DNS name), where Backstage's frontend would throw
// "crypto.randomUUID is not a function" once signed in. getRandomValues works in any context.
// Imported first in index.tsx; a no-op wherever the browser provides randomUUID.
if (typeof globalThis.crypto?.randomUUID !== 'function' && typeof globalThis.crypto?.getRandomValues === 'function') {
  const randomUUID = (): `${string}-${string}-${string}-${string}-${string}` => {
    const b = globalThis.crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40; // version 4
    b[8] = (b[8] & 0x3f) | 0x80; // RFC 4122 variant
    const h = Array.from(b, x => x.toString(16).padStart(2, '0')).join('');
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  };
  Object.defineProperty(globalThis.crypto, 'randomUUID', { value: randomUUID, configurable: true });
}

export {};

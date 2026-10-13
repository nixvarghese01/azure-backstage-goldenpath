import { test } from 'node:test';
import assert from 'node:assert/strict';
import { GET as ready } from '../app/health/ready/route.js';
import { GET as orders } from '../app/v1/orders/route.js';

test('readiness and API route handlers expose the deployment contract', async () => {
  assert.equal((await ready().json()).status, 'ok');
  assert.equal((await orders().json())[0].id, 'demo-001');
});

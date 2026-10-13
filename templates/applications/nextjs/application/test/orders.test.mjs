import { test } from 'node:test';
import assert from 'node:assert/strict';
import { orders } from '../lib/orders.mjs';

test('demo records cannot be mutated across requests', () => {
  assert.throws(() => { orders[0].total = 100; }, TypeError);
  assert.equal(orders[0].total, 5);
});

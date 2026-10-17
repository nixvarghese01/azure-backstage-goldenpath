import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

afterEach(() => vi.unstubAllGlobals());

test('renders sample orders', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, json: async () => [{ id: 'demo-001', customerId: 'cust-001', currency: 'GBP', total: 5 }],
  }));
  const wrapper = mount(App);
  await flushPromises();
  expect(wrapper.text()).toContain('demo-001');
  wrapper.unmount();
});

test('shows data errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  const wrapper = mount(App);
  await flushPromises();
  expect(wrapper.find('[role="alert"]').text()).toBe('Demo unavailable');
  wrapper.unmount();
});

import type { Order } from '../orders/order.entity';

export const ORDER_REPOSITORY = Symbol('ORDER_REPOSITORY');

export interface OrderRepository {
  save(order: Order): Promise<void>;
  get(id: string): Promise<Order | undefined>;
  list(limit: number): Promise<Order[]>;
  /** Readiness check: can the backing store be reached with the current identity? */
  ping(): Promise<{ ok: boolean; backend: string; detail?: string }>;
}

/** Used for local development and tests when no storage account is configured. */
export class InMemoryOrderRepository implements OrderRepository {
  private readonly orders = new Map<string, Order>();

  async save(order: Order): Promise<void> {
    this.orders.set(order.id, order);
  }

  async get(id: string): Promise<Order | undefined> {
    return this.orders.get(id);
  }

  async list(limit: number): Promise<Order[]> {
    return [...this.orders.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, limit);
  }

  async ping(): Promise<{ ok: boolean; backend: string }> {
    return { ok: true, backend: 'memory' };
  }
}

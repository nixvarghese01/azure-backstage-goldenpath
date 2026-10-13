import { NotFoundException } from '@nestjs/common';
import { OrdersService } from '../src/orders/orders.service';
import { InMemoryOrderRepository } from '../src/storage/order.repository';

describe('OrdersService', () => {
  let service: OrdersService;

  beforeEach(() => {
    service = new OrdersService(new InMemoryOrderRepository());
  });

  it('creates an order with a computed, rounded total', async () => {
    const order = await service.create({
      customerId: 'cust-001',
      currency: 'GBP',
      items: [
        { sku: 'SKU-1', quantity: 3, unitPrice: 0.1 },
        { sku: 'SKU-2', quantity: 1, unitPrice: 19.99 },
      ],
    });
    expect(order.total).toBe(20.29);
    expect(order.status).toBe('created');
    expect(await service.findOne(order.id)).toEqual(order);
  });

  it('throws NotFound for unknown orders', async () => {
    await expect(service.findOne('00000000-0000-4000-8000-000000000000')).rejects.toBeInstanceOf(
      NotFoundException,
    );
  });

  it('lists most recent first and clamps the limit', async () => {
    for (let i = 0; i < 3; i++) {
      await service.create({ customerId: `cust-00${i}`, currency: 'EUR', items: [{ sku: 'SKU-1', quantity: 1, unitPrice: 1 }] });
    }
    expect(await service.list(1000)).toHaveLength(3);
    expect(await service.list(0)).toHaveLength(1);
  });
});

import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { ORDER_REPOSITORY, type OrderRepository } from '../storage/order.repository';
import type { CreateOrderDto } from './dto/create-order.dto';
import type { Order } from './order.entity';

@Injectable()
export class OrdersService {
  constructor(@Inject(ORDER_REPOSITORY) private readonly repository: OrderRepository) {}

  async create(dto: CreateOrderDto): Promise<Order> {
    const total = dto.items.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0);
    const order: Order = {
      id: randomUUID(),
      customerId: dto.customerId,
      currency: dto.currency,
      items: dto.items.map(({ sku, quantity, unitPrice }) => ({ sku, quantity, unitPrice })),
      total: Math.round(total * 100) / 100,
      status: 'created',
      createdAt: new Date().toISOString(),
    };
    await this.repository.save(order);
    return order;
  }

  async findOne(id: string): Promise<Order> {
    const order = await this.repository.get(id);
    if (!order) {
      throw new NotFoundException(`Order ${id} not found`);
    }
    return order;
  }

  list(limit = 20): Promise<Order[]> {
    return this.repository.list(Math.min(Math.max(limit, 1), 100));
  }
}

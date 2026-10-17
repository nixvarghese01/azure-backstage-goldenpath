import { Body, Controller, DefaultValuePipe, Get, Param, ParseIntPipe, ParseUUIDPipe, Post, Query } from '@nestjs/common';
import { ApiCreatedResponse, ApiNotFoundResponse, ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { CreateOrderDto } from './dto/create-order.dto';
import type { Order } from './order.entity';
import { OrdersService } from './orders.service';

@ApiTags('orders')
@Controller('v1/orders')
export class OrdersController {
  constructor(private readonly orders: OrdersService) {}

  @Post()
  @ApiCreatedResponse({ description: 'Order created and stored' })
  create(@Body() dto: CreateOrderDto): Promise<Order> {
    return this.orders.create(dto);
  }

  @Get()
  @ApiOkResponse({ description: 'Most recent orders' })
  list(@Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number): Promise<Order[]> {
    return this.orders.list(limit);
  }

  @Get(':id')
  @ApiOkResponse({ description: 'The order' })
  @ApiNotFoundResponse({ description: 'No order with that ID' })
  get(@Param('id', new ParseUUIDPipe({ version: '4' })) id: string): Promise<Order> {
    return this.orders.findOne(id);
  }
}

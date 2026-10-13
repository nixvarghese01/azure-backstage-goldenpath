import { ApiProperty } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import {
  ArrayMaxSize,
  ArrayMinSize,
  IsIn,
  IsInt,
  IsNumber,
  IsString,
  Matches,
  Max,
  Min,
  ValidateNested,
} from 'class-validator';
import type { Currency } from '../order.entity';

export class CreateOrderItemDto {
  @ApiProperty({ example: 'SKU-12345' })
  @IsString()
  @Matches(/^[A-Z0-9-]{3,32}$/)
  sku: string;

  @ApiProperty({ example: 2, minimum: 1, maximum: 100 })
  @IsInt()
  @Min(1)
  @Max(100)
  quantity: number;

  @ApiProperty({ example: 19.99, minimum: 0 })
  @IsNumber({ maxDecimalPlaces: 2 })
  @Min(0)
  @Max(100000)
  unitPrice: number;
}

export class CreateOrderDto {
  @ApiProperty({ example: 'cust-001' })
  @IsString()
  @Matches(/^[a-z0-9-]{3,64}$/)
  customerId: string;

  @ApiProperty({ enum: ['GBP', 'EUR', 'USD'] })
  @IsIn(['GBP', 'EUR', 'USD'])
  currency: Currency;

  @ApiProperty({ type: [CreateOrderItemDto] })
  @ValidateNested({ each: true })
  @Type(() => CreateOrderItemDto)
  @ArrayMinSize(1)
  @ArrayMaxSize(50)
  items: CreateOrderItemDto[];
}

import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { validateConfig } from './config/configuration';
import { HealthModule } from './health/health.module';
import { OrdersModule } from './orders/orders.module';
import { StorageModule } from './storage/storage.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, validate: validateConfig, cache: true }),
    StorageModule,
    OrdersModule,
    HealthModule,
  ],
})
export class AppModule {}

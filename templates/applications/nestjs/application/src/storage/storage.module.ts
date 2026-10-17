import { Global, Logger, Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { BlobOrderRepository } from './blob-order.repository';
import { InMemoryOrderRepository, ORDER_REPOSITORY, type OrderRepository } from './order.repository';

@Global()
@Module({
  providers: [
    {
      provide: ORDER_REPOSITORY,
      inject: [ConfigService],
      useFactory: (config: ConfigService): OrderRepository => {
        const account = config.get<string>('AZURE_STORAGE_ACCOUNT');
        if (!account) {
          Logger.warn('AZURE_STORAGE_ACCOUNT not set: using the in-memory store', 'Storage');
          return new InMemoryOrderRepository();
        }
        return new BlobOrderRepository(account, config.get<string>('AZURE_STORAGE_CONTAINER', 'app-data'));
      },
    },
  ],
  exports: [ORDER_REPOSITORY],
})
export class StorageModule {}

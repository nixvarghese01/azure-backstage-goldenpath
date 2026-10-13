import { DefaultAzureCredential } from '@azure/identity';
import { BlobServiceClient, type ContainerClient } from '@azure/storage-blob';
import type { Order } from '../orders/order.entity';
import type { OrderRepository } from './order.repository';

/**
 * Stores each order as a JSON blob. Authenticates with DefaultAzureCredential, which picks up the pod's
 * Microsoft Entra Workload Identity (no keys, connection strings or SAS tokens anywhere).
 */
export class BlobOrderRepository implements OrderRepository {
  private readonly container: ContainerClient;

  constructor(accountName: string, containerName: string) {
    const service = new BlobServiceClient(
      `https://${accountName}.blob.core.windows.net`,
      new DefaultAzureCredential(),
    );
    this.container = service.getContainerClient(containerName);
  }

  private blobName(id: string): string {
    return `orders/${id}.json`;
  }

  async save(order: Order): Promise<void> {
    const body = JSON.stringify(order);
    await this.container
      .getBlockBlobClient(this.blobName(order.id))
      .upload(body, Buffer.byteLength(body), { blobHTTPHeaders: { blobContentType: 'application/json' } });
  }

  async get(id: string): Promise<Order | undefined> {
    const blob = this.container.getBlockBlobClient(this.blobName(id));
    if (!(await blob.exists())) {
      return undefined;
    }
    const buffer = await blob.downloadToBuffer();
    return JSON.parse(buffer.toString('utf8')) as Order;
  }

  async list(limit: number): Promise<Order[]> {
    const orders: Order[] = [];
    for await (const item of this.container.listBlobsFlat({ prefix: 'orders/' })) {
      const order = await this.get(item.name.replace(/^orders\//, '').replace(/\.json$/, ''));
      if (order) orders.push(order);
      if (orders.length >= 500) break;
    }
    return orders.sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, limit);
  }

  async ping(): Promise<{ ok: boolean; backend: string; detail?: string }> {
    try {
      await this.container.getProperties();
      return { ok: true, backend: 'azure-blob' };
    } catch (error) {
      const code = (error as { statusCode?: number }).statusCode;
      return { ok: false, backend: 'azure-blob', detail: code ? `HTTP ${code}` : 'unreachable' };
    }
  }
}

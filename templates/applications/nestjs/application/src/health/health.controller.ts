import { Controller, Get, Inject, ServiceUnavailableException } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { ORDER_REPOSITORY, type OrderRepository } from '../storage/order.repository';

@ApiTags('health')
@Controller('health')
export class HealthController {
  constructor(@Inject(ORDER_REPOSITORY) private readonly repository: OrderRepository) {}

  /** Liveness: the process is up. Never checks dependencies (avoids restart storms). */
  @Get('live')
  live(): { status: 'ok' } {
    return { status: 'ok' };
  }

  /** Readiness: dependencies reachable with the pod's Workload Identity. */
  @Get('ready')
  async ready(): Promise<{ status: 'ok'; storage: { ok: boolean; backend: string } }> {
    const storage = await this.repository.ping();
    if (!storage.ok) {
      throw new ServiceUnavailableException({ status: 'error', storage });
    }
    return { status: 'ok', storage: { ok: storage.ok, backend: storage.backend } };
  }
}

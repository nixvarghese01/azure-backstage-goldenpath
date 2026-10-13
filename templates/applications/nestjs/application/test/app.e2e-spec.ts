import { type INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';

describe('API (e2e, in-memory storage)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    delete process.env.AZURE_STORAGE_ACCOUNT;
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it('GET /health/live and /health/ready', async () => {
    await request(app.getHttpServer()).get('/health/live').expect(200, { status: 'ok' });
    const ready = await request(app.getHttpServer()).get('/health/ready').expect(200);
    expect(ready.body.storage.backend).toBe('memory');
  });

  it('creates, reads and lists orders', async () => {
    const created = await request(app.getHttpServer())
      .post('/v1/orders')
      .send({ customerId: 'cust-001', currency: 'GBP', items: [{ sku: 'SKU-1', quantity: 2, unitPrice: 5 }] })
      .expect(201);
    await request(app.getHttpServer()).get(`/v1/orders/${created.body.id}`).expect(200);
    const list = await request(app.getHttpServer()).get('/v1/orders').expect(200);
    expect(list.body).toHaveLength(1);
  });

  it('rejects invalid input and unknown fields', async () => {
    await request(app.getHttpServer())
      .post('/v1/orders')
      .send({ customerId: 'x', currency: 'BTC', items: [], admin: true })
      .expect(400);
  });

  it('rejects malformed IDs', async () => {
    await request(app.getHttpServer()).get('/v1/orders/not-a-uuid').expect(400);
  });
});

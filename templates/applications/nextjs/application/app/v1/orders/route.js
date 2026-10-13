import { orders } from '../../../lib/orders.mjs';
export function GET() { return Response.json(orders); }

export type Currency = 'GBP' | 'EUR' | 'USD';

export interface OrderItem {
  sku: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  id: string;
  customerId: string;
  currency: Currency;
  items: OrderItem[];
  total: number;
  status: 'created';
  createdAt: string;
}

import './style.css';

export const metadata = { title: 'Service starter', description: 'A Docker-ready platform starter' };

export default function RootLayout({ children }) {
  return <html lang="en"><body>{children}</body></html>;
}

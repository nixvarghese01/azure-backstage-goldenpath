export default function Docs() {
  return <main><h1>Starter endpoints</h1><p>This project serves read-only sample data.</p>
    <ul>{['/health/live', '/health/ready', '/v1/orders'].map(path =>
      <li key={path}><a href={path}>{path}</a></li>)}</ul><a href="/">Home</a>
  </main>;
}

import './polyfills';
import '@backstage/cli/asset-types';
// Inter, bundled with the app (no external font request).
import '@fontsource-variable/inter';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);

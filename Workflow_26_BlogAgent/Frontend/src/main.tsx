import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: '#1a2d45',
          color: '#e8edf2',
          border: '1px solid rgba(251, 191, 36, 0.2)',
          fontFamily: '"DM Sans", sans-serif',
          fontSize: '14px',
          borderRadius: '10px',
        },
        success: { iconTheme: { primary: '#34d399', secondary: '#0a1929' } },
        error:   { iconTheme: { primary: '#fb7185', secondary: '#0a1929' } },
      }}
    />
  </React.StrictMode>
)

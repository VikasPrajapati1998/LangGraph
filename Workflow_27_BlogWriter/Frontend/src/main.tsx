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
      gutter={10}
      toastOptions={{
        duration: 3500,
        style: {
          background: 'rgba(13, 22, 41, 0.95)',
          color: '#e2e8f8',
          border: '1px solid rgba(139, 92, 246, 0.3)',
          fontFamily: '"Inter", sans-serif',
          fontSize: '13px',
          borderRadius: '12px',
          backdropFilter: 'blur(20px)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(139,92,246,0.1)',
          padding: '12px 16px',
        },
        success: {
          iconTheme: { primary: '#10b981', secondary: '#030712' },
          style: { borderColor: 'rgba(16, 185, 129, 0.3)' },
        },
        error: {
          iconTheme: { primary: '#f43f5e', secondary: '#030712' },
          style: { borderColor: 'rgba(244, 63, 94, 0.3)' },
        },
      }}
    />
  </React.StrictMode>
)

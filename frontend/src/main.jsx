import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Note: no <StrictMode> wrapper. It double-mounts components in dev, which opens
// the camera/MJPEG streams twice and made detection score each dart twice. The
// server also guards against overlapping detection sessions, but not mounting
// twice keeps camera startup clean.
createRoot(document.getElementById('root')).render(<App />)

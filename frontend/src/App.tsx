import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import VoicemailPage from './pages/VoicemailPage';
import Admin from './pages/Admin';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="voicemail/:id" element={<VoicemailPage />} />
        <Route path="admin" element={<Admin />} />
      </Route>
    </Routes>
  );
}

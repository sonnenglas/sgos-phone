import { useState, useEffect } from 'react';
import { Outlet, Link } from 'react-router-dom';
import { api } from '../api';

export default function Layout() {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(data => setEmail(data.email)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="text-xl font-medium tracking-tight hover:opacity-60 transition-opacity duration-150">
            Phone
          </Link>
          <div className="flex items-center gap-6">
            {email && (
              <span className="text-sm text-secondary">{email}</span>
            )}
            <Link to="/admin" className="text-sm text-secondary hover:text-black transition-colors duration-150">
              Admin
            </Link>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-12">
        <Outlet />
      </main>
    </div>
  );
}

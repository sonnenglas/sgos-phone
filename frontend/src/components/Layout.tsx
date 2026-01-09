import { Outlet, Link } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="text-xl font-medium tracking-tight hover:opacity-60 transition-opacity duration-150">
            Voicemail
          </Link>
          <Link to="/admin" className="text-sm text-secondary hover:text-black transition-colors duration-150">
            Admin
          </Link>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-12">
        <Outlet />
      </main>
    </div>
  );
}

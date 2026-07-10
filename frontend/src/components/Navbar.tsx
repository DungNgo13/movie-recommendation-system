import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuthHook';
import { getAvatarUrl } from '../utils/avatarUrl';

const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    navigate('/', { replace: true });
    // Defer the state clear so ProtectedRouter doesn't intercept the navigation
    setTimeout(() => {
      logout();
    }, 0);
  };

  /** Return 'active' class when current path matches the link target */
  const navClass = (path: string) => {
    const exactMatchRequired = ['/', '/admin', '/favorites'].includes(path);
    const isActive = exactMatchRequired
      ? location.pathname === path
      : location.pathname.startsWith(path);
    return `navbar-link${isActive ? ' active' : ''}`;
  };

  const avatarSrc = getAvatarUrl(user?.avatar_url);
  const initial = user?.email?.charAt(0).toUpperCase() || 'U';

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">Laetus</Link>
      <div className="navbar-links">
        <Link to="/" className={navClass('/')}>Home</Link>
        <Link to="/favorites" className={navClass('/favorites')}>Favorites</Link>
        {user?.role === 'admin' && (
          <>
            <Link to="/admin" className={navClass('/admin')}>Dashboard</Link>
            <Link to="/admin/movies" className={navClass('/admin/movies')}>Movies</Link>
            <Link to="/admin/users" className={navClass('/admin/users')}>Users</Link>
            <Link to="/admin/logs" className={navClass('/admin/logs')}>Logs</Link>
            <Link to="/admin/recsys" className={navClass('/admin/recsys')}>RecSys</Link>
            <Link to="/admin/security" className={navClass('/admin/security')}>Security</Link>
          </>
        )}
        {user ? (
          <>
            <Link to="/profile" className="navbar-profile-block" title="My Profile">
              {avatarSrc ? (
                <img
                  src={avatarSrc}
                  alt=""
                  className="navbar-avatar"
                  onError={(e) => {
                    // Hide broken image, show fallback placeholder
                    e.currentTarget.style.display = 'none';
                    const next = e.currentTarget.nextElementSibling as HTMLElement | null;
                    if (next) next.style.display = '';
                  }}
                />
              ) : null}
              <span
                className="navbar-avatar-placeholder"
                style={avatarSrc ? { display: 'none' } : undefined}
              >
                {initial}
              </span>
              <span className="navbar-profile-email">{user.email}</span>
            </Link>
            <button className="navbar-link navbar-logout" onClick={handleLogout}>
              Logout
            </button>
          </>
        ) : (
          <Link to="/login" className="navbar-link navbar-login">Login</Link>
        )}
      </div>
    </nav>
  );
};

export default Navbar;

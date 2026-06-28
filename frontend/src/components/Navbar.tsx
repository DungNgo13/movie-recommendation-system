import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

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
    const isActive =
      path === '/'
        ? location.pathname === '/'
        : location.pathname.startsWith(path);
    return `navbar-link${isActive ? ' active' : ''}`;
  };

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
              {user.avatar_url ? (
                <img src={user.avatar_url} alt="" className="navbar-avatar" />
              ) : (
                <span className="navbar-avatar-placeholder">
                  {user.email?.charAt(0).toUpperCase() || 'U'}
                </span>
              )}
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

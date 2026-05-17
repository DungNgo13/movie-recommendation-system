import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    navigate('/', { replace: true });
    // Defer the state clear so ProtectedRouter doesn't intercept the navigation
    setTimeout(() => {
      logout();
    }, 0);
  };

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">🎬 Movies</Link>
      <div className="navbar-links">
        <Link to="/" className="navbar-link">Home</Link>
        <Link to="/favorites" className="navbar-link">♥ Favorites</Link>
        {user?.role === 'admin' && (
          <>
            <Link to="/admin" className="navbar-link">📊 Dashboard</Link>
            <Link to="/admin/movies" className="navbar-link">⚙ Movies</Link>
            <Link to="/admin/users" className="navbar-link">👥 Users</Link>
            <Link to="/admin/logs" className="navbar-link">📋 Logs</Link>
            <Link to="/admin/recsys" className="navbar-link">🔬 RecSys</Link>
            <Link to="/admin/security" className="navbar-link">🛡️ Security</Link>
          </>
        )}
        {user ? (
          <>
            <Link to="/profile" className="navbar-profile-block" title="My Profile">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt="" className="navbar-avatar" />
              ) : (
                <span className="navbar-avatar-placeholder">👤</span>
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

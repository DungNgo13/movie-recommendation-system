import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">🎬 Movies</Link>
      <div className="navbar-links">
        <Link to="/" className="navbar-link">Home</Link>
        <Link to="/favorites" className="navbar-link">♥ Favorites</Link>
        {user?.role === 'admin' && (
          <>
            <Link to="/admin/movies" className="navbar-link">⚙ Admin</Link>
            <Link to="/admin/users" className="navbar-link">👥 Users</Link>
          </>
        )}
        {user ? (
          <>
            <span className="navbar-user">{user.email}</span>
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

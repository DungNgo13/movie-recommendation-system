import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const Navbar: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">🎬 Movies</Link>
      <div className="navbar-links">
        <Link to="/" className="navbar-link">Home</Link>
        <Link to="/favorites" className="navbar-link">♥ Favorites</Link>
        <Link to="/admin/movies" className="navbar-link">⚙ Admin</Link>
        {user ? (
          <>
            <span className="navbar-user">{user.email}</span>
            <button className="navbar-link navbar-logout" onClick={logout}>
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

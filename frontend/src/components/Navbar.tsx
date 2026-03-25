import React from 'react';
import { Link } from 'react-router-dom';

const Navbar: React.FC = () => {
  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">🎬 Movies</Link>
      <div className="navbar-links">
        <Link to="/" className="navbar-link">Home</Link>
        <Link to="/favorites" className="navbar-link">♥ Favorites</Link>
      </div>
    </nav>
  );
};

export default Navbar;

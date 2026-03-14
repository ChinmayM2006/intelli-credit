import React from 'react';
import { Link } from 'react-router-dom';

function Navbar() {
  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        <span>🏦</span>
        <h1>Intelli-Credit</h1>
      </Link>
      <div className="navbar-links">
        <Link to="/">Dashboard</Link>
      </div>
    </nav>
  );
}

export default Navbar;

import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';
import MovieDetailPage from './pages/MovieDetailPage';
import FavoritesPage from './pages/FavoritesPage';
import AdminMoviesPage from './pages/AdminMoviesPage';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="App">
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/movie/:id" element={<MovieDetailPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/admin/movies" element={<AdminMoviesPage />} />
      </Routes>
    </div>
  );
};

export default App;

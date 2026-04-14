import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';
import MovieDetailPage from './pages/MovieDetailPage';
import FavoritesPage from './pages/FavoritesPage';
import AdminMoviesPage from './pages/AdminMoviesPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminAuditLogsPage from './pages/AdminAuditLogsPage';
import RecsysMonitorPage from './pages/RecsysMonitorPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ProtectedAdminRoute from './components/ProtectedAdminRoute';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="App">
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/movie/:id" element={<MovieDetailPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        
        <Route element={<ProtectedAdminRoute />}>
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="/admin/movies" element={<AdminMoviesPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/logs" element={<AdminAuditLogsPage />} />
          <Route path="/admin/recsys" element={<RecsysMonitorPage />} />
        </Route>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Routes>
    </div>
  );
};

export default App;

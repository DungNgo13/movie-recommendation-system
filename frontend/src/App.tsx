import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import SiteFooter from './components/SiteFooter';
import HomePage from './pages/HomePage';
import MovieDetailPage from './pages/MovieDetailPage';
import FavoritesPage from './pages/FavoritesPage';
import AdminMoviesPage from './pages/AdminMoviesPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminAuditLogsPage from './pages/AdminAuditLogsPage';
import RecsysMonitorPage from './pages/RecsysMonitorPage';
import AdminSecurityAuditPage from './pages/AdminSecurityAuditPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import ProfilePage from './pages/ProfilePage';
import ConfirmPasswordChangePage from './pages/ConfirmPasswordChangePage';
import ProtectedAdminRoute from './components/ProtectedAdminRoute';
import { useAutoRefreshSession } from './hooks/useAutoRefreshSession';
import './App.css';

const App: React.FC = () => {
  // Sliding session — silently refreshes the JWT when the user is active
  // and the token reaches 50% of its lifetime. Runs in the background
  // with zero re-renders; does not interrupt the HLS player.
  useAutoRefreshSession();
  return (
    <div className="app-shell">
      <Navbar />

      <main className="app-main">
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
            <Route path="/admin/security" element={<AdminSecurityAuditPage />} />
          </Route>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/confirm-password-change" element={<ConfirmPasswordChangePage />} />
        </Routes>
      </main>

      <SiteFooter />
    </div>
  );
};

export default App;


import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import AvatarUpload from '../components/AvatarUpload';
import ChangePasswordForm from '../components/ChangePasswordForm';

const ProfilePage: React.FC = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="loading-spinner">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="profile-page" id="profile-page">
      <h1>My Profile</h1>

      <div className="profile-page__grid">
        {/* Avatar Section */}
        <section className="profile-section">
          <h2>Profile Picture</h2>
          <AvatarUpload />
        </section>

        {/* Password Section */}
        <section className="profile-section">
          <ChangePasswordForm />
        </section>
      </div>
    </div>
  );
};

export default ProfilePage;

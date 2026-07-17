import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuthHook';
import AvatarUpload from '../components/AvatarUpload';
import ChangePasswordForm from '../components/ChangePasswordForm';
import { useTranslation } from 'react-i18next';

const ProfilePage: React.FC = () => {
  const { user, loading } = useAuth();
  const { t } = useTranslation(['auth']);

  if (loading) {
    return <div className="loading-spinner">{t("auth:profile.loading")}</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="profile-page" id="profile-page">
      <h1>{t("auth:profile.myProfile")}</h1>

      <div className="profile-page__grid">
        {/* Avatar Section */}
        <section className="profile-section">
          <h2>{t("auth:profile.profilePicture")}</h2>
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

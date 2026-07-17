import React from 'react';
import { useTranslation } from 'react-i18next';

const LoadingSpinner: React.FC = () => {
  const { t } = useTranslation(['common']);
  return <div className="loading-spinner">{t("common:loading", "Loading...")}</div>;
};

export default LoadingSpinner;

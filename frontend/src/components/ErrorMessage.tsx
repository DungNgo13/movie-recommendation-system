import React from 'react';
import { useTranslation } from 'react-i18next';

interface ErrorMessageProps {
  message: string;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message }) => {
  const { t } = useTranslation(['common']);
  return <div className="error-message">{t("common:errorPrefix", "Error:")} {message}</div>;
};

export default ErrorMessage;

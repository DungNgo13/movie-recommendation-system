import React from 'react';
import { useTranslation } from 'react-i18next';

const SiteFooter: React.FC = () => {
  const { t } = useTranslation('common');

  return (
    <footer
      className="site-footer"
      aria-label={t("footer.ariaLabel", "Site footer")}
    >
      <div className="site-footer__inner">
        <p className="site-footer__copyright">
          © {new Date().getFullYear()} Laetus
        </p>

        <p className="site-footer__disclaimer">
          {t("footer.disclaimer")}
        </p>
      </div>
    </footer>
  );
};

export default SiteFooter;

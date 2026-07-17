import React from "react";
import { useTranslation } from "react-i18next";
import { saveLanguage, AppLanguage } from "../i18n/languageStorage";

export const LanguageSelector: React.FC = () => {
  const { t, i18n } = useTranslation();

  const handleLanguageChange = (lang: AppLanguage) => {
    i18n.changeLanguage(lang);
    saveLanguage(lang);
  };

  const isVi = i18n.language === "vi";
  const isEn = i18n.language === "en";

  return (
    <div
      className="language-selector"
      role="group"
      aria-label={t("common:language.title")}
    >
      <button
        type="button"
        className={`lang-btn ${isVi ? "active" : ""}`}
        onClick={() => handleLanguageChange("vi")}
        aria-pressed={isVi}
        title={t("common:language.vi")}
      >
        VI
      </button>
      <span className="lang-divider">|</span>
      <button
        type="button"
        className={`lang-btn ${isEn ? "active" : ""}`}
        onClick={() => handleLanguageChange("en")}
        aria-pressed={isEn}
        title={t("common:language.en")}
      >
        EN
      </button>
    </div>
  );
};

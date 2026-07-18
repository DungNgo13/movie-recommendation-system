import React from "react";
import { useTranslation } from "react-i18next";
import { saveLanguage } from "../i18n/languageStorage";
import type { AppLanguage } from "../i18n/languageStorage";

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
      className="segmented-control"
      role="group"
      aria-label={t("common:language.title")}
    >
      <button
        type="button"
        className={`segmented-control__option${isVi ? " segmented-control__option--active" : ""}`}
        onClick={() => handleLanguageChange("vi")}
        aria-pressed={isVi}
        title={t("common:language.vi")}
      >
        VI
      </button>
      <button
        type="button"
        className={`segmented-control__option${isEn ? " segmented-control__option--active" : ""}`}
        onClick={() => handleLanguageChange("en")}
        aria-pressed={isEn}
        title={t("common:language.en")}
      >
        EN
      </button>
    </div>
  );
};

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { loadLanguage } from "./languageStorage";

// Import English locales
import enCommon from "./locales/en/common.json";
import enAuth from "./locales/en/auth.json";
import enMovies from "./locales/en/movies.json";
import enAdmin from "./locales/en/admin.json";
import enRecommendation from "./locales/en/recommendation.json";

// Import Vietnamese locales
import viCommon from "./locales/vi/common.json";
import viAuth from "./locales/vi/auth.json";
import viMovies from "./locales/vi/movies.json";
import viAdmin from "./locales/vi/admin.json";
import viRecommendation from "./locales/vi/recommendation.json";

const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    movies: enMovies,
    admin: enAdmin,
    recommendation: enRecommendation,
  },
  vi: {
    common: viCommon,
    auth: viAuth,
    movies: viMovies,
    admin: viAdmin,
    recommendation: viRecommendation,
  },
};

const initialLanguage = loadLanguage();
document.documentElement.lang = initialLanguage;

i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage,
  fallbackLng: "en",
  ns: ["common", "auth", "movies", "admin", "recommendation"],
  defaultNS: "common",
  interpolation: {
    escapeValue: false, // React already escapes values
  },
});

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});

export default i18n;

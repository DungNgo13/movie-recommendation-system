export type AppLanguage = "vi" | "en";

export const LANGUAGE_STORAGE_KEY = "movie-app-language";

export function isAppLanguage(value: unknown): value is AppLanguage {
  return value === "vi" || value === "en";
}

export function loadLanguage(): AppLanguage {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isAppLanguage(stored)) {
      return stored;
    }
  } catch (error) {
    console.error("Failed to load language from localStorage:", error);
  }
  return "vi";
}

export function saveLanguage(language: AppLanguage): void {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch (error) {
    console.error("Failed to save language to localStorage:", error);
  }
}

import { AppLanguage } from "../i18n/languageStorage";

interface LocalizedMovieFields {
  title: string;
  title_vi?: string | null;
  overview?: string | null;
  overview_vi?: string | null;
  keyword_labels_vi?: Record<string, string> | null;
}

function normalizeStr(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function getLocalizedTitle(
  movie: LocalizedMovieFields,
  language: AppLanguage
): string {
  if (language === "vi") {
    const vi = normalizeStr(movie.title_vi);
    if (vi) return vi;
  }
  return movie.title;
}

export function getLocalizedOverview(
  movie: LocalizedMovieFields,
  language: AppLanguage
): string {
  if (language === "vi") {
    const vi = normalizeStr(movie.overview_vi);
    if (vi) return vi;
  }
  return normalizeStr(movie.overview) || "";
}

export function getLocalizedKeywordLabel(
  canonicalKeyword: string,
  keywordLabelsVi: Record<string, string> | null | undefined,
  language: AppLanguage
): string {
  if (language === "vi" && keywordLabelsVi) {
    const vi = normalizeStr(keywordLabelsVi[canonicalKeyword]);
    if (vi) return vi;
  }
  return canonicalKeyword;
}

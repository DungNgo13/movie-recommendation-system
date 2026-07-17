import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface StarRatingProps {
  currentRating: number | null;
  onRate: (rating: number) => void | Promise<void>;
  disabled?: boolean;
}

/**
 * Inline SVG star icon — used by StarRating.
 * Renders a filled (gold) or outlined (gray) 5-pointed star.
 */
const StarIcon: React.FC<{ filled: boolean; size?: number }> = ({ filled, size = 28 }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    aria-hidden="true"
    focusable="false"
    className="star-btn__icon"
  >
    <path
      d="M12 2l3.09 6.26L22 9.27l-5 4.87
         1.18 6.88L12 17.77l-6.18 3.25L7 14.14
         2 9.27l6.91-1.01L12 2z"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
  </svg>
);

const StarRating: React.FC<StarRatingProps> = ({ currentRating, onRate, disabled }) => {
  const [hoverRating, setHoverRating] = useState(0);
  const { t } = useTranslation(['movies']);

  return (
    <div
      className="star-rating"
      onMouseLeave={() => !disabled && setHoverRating(0)}
    >
      {[1, 2, 3, 4, 5].map((star) => {
        const displayRating = hoverRating || currentRating || 0;
        const isFilled = star <= displayRating;
        return (
          <button
            key={star}
            type="button"
            className={`star-btn${isFilled ? ' star-btn--filled' : ''}`}
            onClick={() => !disabled && onRate(star)}
            onMouseEnter={() => !disabled && setHoverRating(star)}
            disabled={disabled}
            aria-label={t("movies:starRating.rate", "Rate {{star}} out of 5", { star })}
            aria-pressed={star <= (currentRating || 0)}
            title={t("movies:starRating.outOf", "{{star}} out of 5", { star })}
          >
            <StarIcon filled={isFilled} />
          </button>
        );
      })}
    </div>
  );
};

export default StarRating;

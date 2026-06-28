import React, { useState } from 'react';

interface StarRatingProps {
  currentRating: number | null;
  onRate: (rating: number) => void;
  disabled?: boolean;
}

const StarRating: React.FC<StarRatingProps> = ({ currentRating, onRate, disabled }) => {
  const [hoverRating, setHoverRating] = useState(0);

  return (
    <div className="star-rating">
      {[1, 2, 3, 4, 5].map((star) => {
        const isFilled = star <= (hoverRating || currentRating || 0);
        return (
          <button
            key={star}
            type="button"
            className={`star-btn${isFilled ? ' star-btn--filled' : ''}`}
            onClick={() => !disabled && onRate(star)}
            onMouseEnter={() => !disabled && setHoverRating(star)}
            onMouseLeave={() => setHoverRating(0)}
            disabled={disabled}
            aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
            title={`${star} star${star > 1 ? 's' : ''}`}
          >
            {star}
          </button>
        );
      })}
    </div>
  );
};

export default StarRating;

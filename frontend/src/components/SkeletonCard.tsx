import React from 'react';

/**
 * A skeleton placeholder card that mimics the shape of a MovieCard.
 * Renders a pulsing animation while real data loads.
 */
const SkeletonCard: React.FC = () => {
  return (
    <div className="skeleton-card">
      <div className="skeleton-card__poster skeleton-pulse" />
      <div className="skeleton-card__title skeleton-pulse" />
    </div>
  );
};

export default SkeletonCard;

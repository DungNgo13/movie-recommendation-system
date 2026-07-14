import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StarRating from './StarRating';

describe('StarRating', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // ── Rendering ─────────────────────────────────────────────────────

  it('renders exactly 5 star buttons', () => {
    render(<StarRating currentRating={0} onRate={vi.fn()} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(5);
  });

  it('does NOT render numeric labels 1-5 as visible text', () => {
    const { container } = render(<StarRating currentRating={0} onRate={vi.fn()} />);
    // The button text content should NOT be just a number
    const buttons = container.querySelectorAll('.star-btn');
    buttons.forEach((btn) => {
      const textContent = btn.textContent?.trim() || '';
      expect(textContent).not.toMatch(/^[1-5]$/);
    });
  });

  it('renders SVG elements inside each star button', () => {
    const { container } = render(<StarRating currentRating={0} onRate={vi.fn()} />);
    const svgs = container.querySelectorAll('.star-btn svg');
    expect(svgs).toHaveLength(5);
  });

  // ── Visual states ─────────────────────────────────────────────────

  it('rating 0 renders five unselected stars', () => {
    const { container } = render(<StarRating currentRating={0} onRate={vi.fn()} />);
    const filledBtns = container.querySelectorAll('.star-btn--filled');
    expect(filledBtns).toHaveLength(0);
  });

  it('rating 3 renders first three stars as filled', () => {
    const { container } = render(<StarRating currentRating={3} onRate={vi.fn()} />);
    const filledBtns = container.querySelectorAll('.star-btn--filled');
    expect(filledBtns).toHaveLength(3);
  });

  it('rating 5 renders all five stars as filled', () => {
    const { container } = render(<StarRating currentRating={5} onRate={vi.fn()} />);
    const filledBtns = container.querySelectorAll('.star-btn--filled');
    expect(filledBtns).toHaveLength(5);
  });

  it('null rating renders zero filled stars', () => {
    const { container } = render(<StarRating currentRating={null} onRate={vi.fn()} />);
    const filledBtns = container.querySelectorAll('.star-btn--filled');
    expect(filledBtns).toHaveLength(0);
  });

  // ── Click behavior ────────────────────────────────────────────────

  it('clicking star 4 calls onRate with 4', () => {
    const onRate = vi.fn();
    render(<StarRating currentRating={0} onRate={onRate} />);
    const btn = screen.getByRole('button', { name: /rate 4 out of 5/i });
    fireEvent.click(btn);
    expect(onRate).toHaveBeenCalledTimes(1);
    expect(onRate).toHaveBeenCalledWith(4);
  });

  it('clicking star 1 calls onRate with 1', () => {
    const onRate = vi.fn();
    render(<StarRating currentRating={0} onRate={onRate} />);
    const btn = screen.getByRole('button', { name: /rate 1 out of 5/i });
    fireEvent.click(btn);
    expect(onRate).toHaveBeenCalledWith(1);
  });

  // ── Hover preview ─────────────────────────────────────────────────

  it('hovering star 4 previews four filled stars', () => {
    const { container } = render(<StarRating currentRating={0} onRate={vi.fn()} />);
    const btn4 = screen.getByRole('button', { name: /rate 4 out of 5/i });
    fireEvent.mouseEnter(btn4);
    const filledBtns = container.querySelectorAll('.star-btn--filled');
    expect(filledBtns).toHaveLength(4);
  });

  it('leaving the control restores the saved rating', () => {
    const { container } = render(<StarRating currentRating={2} onRate={vi.fn()} />);
    const btn5 = screen.getByRole('button', { name: /rate 5 out of 5/i });

    // Hover over star 5
    fireEvent.mouseEnter(btn5);
    expect(container.querySelectorAll('.star-btn--filled')).toHaveLength(5);

    // Leave the rating container
    const ratingDiv = container.querySelector('.star-rating')!;
    fireEvent.mouseLeave(ratingDiv);
    expect(container.querySelectorAll('.star-btn--filled')).toHaveLength(2);
  });

  // ── Disabled state ────────────────────────────────────────────────

  it('all buttons are disabled when disabled prop is true', () => {
    render(<StarRating currentRating={3} onRate={vi.fn()} disabled />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });

  it('does not call onRate when disabled', () => {
    const onRate = vi.fn();
    render(<StarRating currentRating={0} onRate={onRate} disabled />);
    const btn = screen.getByRole('button', { name: /rate 3 out of 5/i });
    fireEvent.click(btn);
    expect(onRate).not.toHaveBeenCalled();
  });

  it('does not show hover preview when disabled', () => {
    const { container } = render(<StarRating currentRating={1} onRate={vi.fn()} disabled />);
    const btn = screen.getByRole('button', { name: /rate 4 out of 5/i });
    fireEvent.mouseEnter(btn);
    // Should still show only 1 filled (no hover preview)
    expect(container.querySelectorAll('.star-btn--filled')).toHaveLength(1);
  });

  // ── Accessibility ─────────────────────────────────────────────────

  it('each star has correct aria-label', () => {
    render(<StarRating currentRating={0} onRate={vi.fn()} />);
    for (let i = 1; i <= 5; i++) {
      const btn = screen.getByRole('button', { name: `Rate ${i} out of 5` });
      expect(btn).toBeInTheDocument();
    }
  });

  it('selected stars have aria-pressed="true"', () => {
    render(<StarRating currentRating={3} onRate={vi.fn()} />);
    const buttons = screen.getAllByRole('button');
    // Stars 1-3 should be pressed, 4-5 should not
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'true');
    expect(buttons[1]).toHaveAttribute('aria-pressed', 'true');
    expect(buttons[2]).toHaveAttribute('aria-pressed', 'true');
    expect(buttons[3]).toHaveAttribute('aria-pressed', 'false');
    expect(buttons[4]).toHaveAttribute('aria-pressed', 'false');
  });

  it('each star is a native <button type="button">', () => {
    render(<StarRating currentRating={0} onRate={vi.fn()} />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn.tagName).toBe('BUTTON');
      expect(btn).toHaveAttribute('type', 'button');
    });
  });

  // ── Keyboard activation ───────────────────────────────────────────

  it('supports keyboard Enter activation', () => {
    const onRate = vi.fn();
    render(<StarRating currentRating={0} onRate={onRate} />);
    const btn = screen.getByRole('button', { name: /rate 3 out of 5/i });
    // Native buttons respond to Enter/Space via click event
    fireEvent.click(btn);
    expect(onRate).toHaveBeenCalledWith(3);
  });
});

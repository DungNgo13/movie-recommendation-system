import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SiteFooter from './SiteFooter';

/* ─── SiteFooter Tests ──────────────────────────────────────────────── */

describe('SiteFooter', () => {
  it('renders a semantic <footer> element', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    const footer = screen.getByRole('contentinfo');
    expect(footer).toBeInTheDocument();
    expect(footer.tagName).toBe('FOOTER');
  });

  it('renders the current year and Laetus', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(`© ${year} Laetus`))).toBeInTheDocument();
  });

  it('renders the English disclaimer text by default (mock returns default value)', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    // The test i18n mock returns the key — "footer.disclaimer"
    // but the SiteFooter uses t("footer.disclaimer") without a default,
    // so the mock returns the key itself
    expect(screen.getByText('footer.disclaimer')).toBeInTheDocument();
  });

  it('has a translated accessible label', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    const footer = screen.getByRole('contentinfo');
    // mock returns default value "Site footer"
    expect(footer).toHaveAttribute('aria-label', 'Site footer');
  });

  it('renders exactly one footer element', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    const footers = screen.getAllByRole('contentinfo');
    expect(footers).toHaveLength(1);
  });

  it('has the site-footer class for styling', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    const footer = screen.getByRole('contentinfo');
    expect(footer.classList.contains('site-footer')).toBe(true);
  });

  it('contains copyright and disclaimer paragraphs', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    const footer = screen.getByRole('contentinfo');
    const paragraphs = footer.querySelectorAll('p');
    expect(paragraphs.length).toBe(2);
    // First paragraph is copyright
    expect(paragraphs[0].classList.contains('site-footer__copyright')).toBe(true);
    // Second paragraph is disclaimer
    expect(paragraphs[1].classList.contains('site-footer__disclaimer')).toBe(true);
  });
});

/* ─── SiteFooter in App layout ───────────────────────────────────────── */

describe('SiteFooter — layout integration', () => {
  it('footer is outside main content when rendered alongside', () => {
    // Simulate the app-shell layout without importing App
    // (avoids Plyr/HlsPlayer matchMedia issues in jsdom)
    render(
      <MemoryRouter>
        <div className="app-shell">
          <main className="app-main">
            <p>Page content</p>
          </main>
          <SiteFooter />
        </div>
      </MemoryRouter>,
    );

    const footer = screen.getByRole('contentinfo');
    const main = screen.getByRole('main');
    expect(main.contains(footer)).toBe(false);
  });

  it('only one global footer is present in the layout', () => {
    render(
      <MemoryRouter>
        <div className="app-shell">
          <main className="app-main">
            <p>Login form</p>
          </main>
          <SiteFooter />
        </div>
      </MemoryRouter>,
    );

    const footers = screen.getAllByRole('contentinfo');
    expect(footers).toHaveLength(1);
  });

  it('footer renders on a non-Home route context', () => {
    render(
      <MemoryRouter initialEntries={['/favorites']}>
        <div className="app-shell">
          <main className="app-main">
            <p>Favorites content</p>
          </main>
          <SiteFooter />
        </div>
      </MemoryRouter>,
    );

    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`© ${new Date().getFullYear()} Laetus`))).toBeInTheDocument();
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SiteFooter from './SiteFooter';

/* ─── Mock auth hook ─────────────────────────────────────────────────── */

const mockUseAuth = vi.fn();
vi.mock('../hooks/useAuthHook', () => ({
  useAuth: () => mockUseAuth(),
}));

/* ─── Mock ThemeProvider via useTheme ─────────────────────────────────── */

vi.mock('../hooks/useTheme', () => ({
  useTheme: () => ({ mode: 'system' as const, setMode: vi.fn() }),
}));

/* ─── Dynamic import to pick up mocks ────────────────────────────────── */

let Navbar: React.FC;
beforeEach(async () => {
  const mod = await import('./Navbar');
  Navbar = mod.default;
});

/* ─── Test Helpers ───────────────────────────────────────────────────── */

function renderNavbar(authOverride?: Record<string, unknown>) {
  const defaultAuth = {
    user: null,
    logout: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    token: null,
  };
  mockUseAuth.mockReturnValue({ ...defaultAuth, ...authOverride });
  return render(<MemoryRouter><Navbar /></MemoryRouter>);
}

const adminUser = {
  id: '1',
  email: 'admin@laetus.io.vn',
  role: 'admin',
  avatar_url: null,
  status: 'active',
};

const regularUser = {
  id: '2',
  email: 'user@example.com',
  role: 'user',
  avatar_url: null,
  status: 'active',
};

/* ─── Tests ──────────────────────────────────────────────────────────── */

describe('Navbar — Structure', () => {
  it('renders one global <nav> element', () => {
    renderNavbar();
    const navs = screen.getAllByRole('navigation');
    expect(navs).toHaveLength(1);
  });

  it('nav has the "navbar" class', () => {
    renderNavbar();
    const nav = screen.getByRole('navigation');
    expect(nav.classList.contains('navbar')).toBe(true);
  });

  it('renders brand link with text "Laetus"', () => {
    renderNavbar();
    const brand = screen.getByText('Laetus');
    expect(brand).toBeInTheDocument();
    expect(brand.classList.contains('navbar-brand')).toBe(true);
    expect(brand.closest('a')).toHaveAttribute('href', '/');
  });

  it('renders the navbar-links container', () => {
    renderNavbar();
    const nav = screen.getByRole('navigation');
    const linksContainer = nav.querySelector('.navbar-links');
    expect(linksContainer).toBeInTheDocument();
  });

  it('brand and navbar-links are separate siblings', () => {
    renderNavbar();
    const nav = screen.getByRole('navigation');
    const brand = nav.querySelector('.navbar-brand');
    const links = nav.querySelector('.navbar-links');
    expect(brand).toBeInTheDocument();
    expect(links).toBeInTheDocument();
    // Both are direct children of nav
    expect(brand?.parentElement).toBe(nav);
    expect(links?.parentElement).toBe(nav);
  });
});

describe('Navbar — Selectors rendered', () => {
  it('renders ThemeSelector (segmented control with theme options)', () => {
    renderNavbar();
    // ThemeSelector renders a group with aria-label containing "Theme" or the t() default
    const themeGroup = screen.getByRole('group', { name: /theme/i });
    expect(themeGroup).toBeInTheDocument();
  });

  it('renders LanguageSelector (segmented control with VI/EN)', () => {
    renderNavbar();
    const viButton = screen.getByText('VI');
    const enButton = screen.getByText('EN');
    expect(viButton).toBeInTheDocument();
    expect(enButton).toBeInTheDocument();
  });
});

describe('Navbar — Guest state', () => {
  it('renders Login link for guests', () => {
    renderNavbar();
    const loginLink = screen.getByText('Login');
    expect(loginLink).toBeInTheDocument();
    expect(loginLink.closest('a')).toHaveAttribute('href', '/login');
  });

  it('does not render Logout for guests', () => {
    renderNavbar();
    expect(screen.queryByText('Logout')).not.toBeInTheDocument();
  });

  it('does not render admin links for guests', () => {
    renderNavbar();
    expect(screen.queryByText('Movies')).not.toBeInTheDocument();
    expect(screen.queryByText('Users')).not.toBeInTheDocument();
  });
});

describe('Navbar — Authenticated user state', () => {
  it('renders Profile link for authenticated user', () => {
    renderNavbar({ user: regularUser });
    const profileLink = screen.getByTitle('My Profile');
    expect(profileLink).toBeInTheDocument();
    expect(profileLink.closest('a')).toHaveAttribute('href', '/profile');
  });

  it('renders Logout button for authenticated user', () => {
    renderNavbar({ user: regularUser });
    const logoutBtn = screen.getByText('Logout');
    expect(logoutBtn).toBeInTheDocument();
    expect(logoutBtn.tagName).toBe('BUTTON');
  });

  it('does not render Login link for authenticated user', () => {
    renderNavbar({ user: regularUser });
    expect(screen.queryByText('Login')).not.toBeInTheDocument();
  });

  it('does not render admin links for regular user', () => {
    renderNavbar({ user: regularUser });
    expect(screen.queryByText('Movies')).not.toBeInTheDocument();
    expect(screen.queryByText('Security')).not.toBeInTheDocument();
  });
});

describe('Navbar — Admin state', () => {
  it('renders admin navigation links for admin users', () => {
    renderNavbar({ user: adminUser });
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Movies')).toBeInTheDocument();
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Logs')).toBeInTheDocument();
    expect(screen.getByText('RecSys')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
  });

  it('admin links point to correct routes', () => {
    renderNavbar({ user: adminUser });
    const dashLink = screen.getByText('Dashboard');
    expect(dashLink.closest('a')).toHaveAttribute('href', '/admin');
    const moviesLink = screen.getByText('Movies');
    expect(moviesLink.closest('a')).toHaveAttribute('href', '/admin/movies');
  });

  it('still renders Logout and Profile for admin', () => {
    renderNavbar({ user: adminUser });
    expect(screen.getByText('Logout')).toBeInTheDocument();
    expect(screen.getByTitle('My Profile')).toBeInTheDocument();
  });
});

describe('Navbar — i18n labels', () => {
  it('Home link renders with translated default value', () => {
    renderNavbar();
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('Favorites link renders with translated default value', () => {
    renderNavbar();
    expect(screen.getByText('Favorites')).toBeInTheDocument();
  });
});

describe('Navbar — Active route highlighting', () => {
  it('Home link has "active" class on / route', () => {
    mockUseAuth.mockReturnValue({ user: null, logout: vi.fn() });
    render(
      <MemoryRouter initialEntries={['/']}>
        <Navbar />
      </MemoryRouter>,
    );
    const homeLink = screen.getByText('Home');
    expect(homeLink.classList.contains('active')).toBe(true);
  });

  it('Favorites link has "active" class on /favorites route', () => {
    mockUseAuth.mockReturnValue({ user: null, logout: vi.fn() });
    render(
      <MemoryRouter initialEntries={['/favorites']}>
        <Navbar />
      </MemoryRouter>,
    );
    const favLink = screen.getByText('Favorites');
    expect(favLink.classList.contains('active')).toBe(true);
  });
});

describe('Navbar — No inline overflow styles', () => {
  it('no element in the navbar has an inline width set to 100vw or a fixed pixel width', () => {
    renderNavbar({ user: adminUser });
    const nav = screen.getByRole('navigation');
    const allElements = nav.querySelectorAll('*');
    allElements.forEach((el) => {
      const style = (el as HTMLElement).style;
      const inlineWidth = style.getPropertyValue('width');
      if (inlineWidth) {
        expect(inlineWidth).not.toContain('100vw');
        // Allow display toggling (used by avatar fallback) but not fixed widths
        expect(inlineWidth).not.toMatch(/^\d{3,}px$/);
      }
    });
  });

  it('navbar itself does not have an inline fixed width or 100vw', () => {
    renderNavbar();
    const nav = screen.getByRole('navigation');
    const inlineWidth = nav.style.getPropertyValue('width');
    expect(inlineWidth).not.toContain('100vw');
    expect(inlineWidth).not.toMatch(/^\d+px$/);
  });
});

describe('Navbar + Footer — App shell layout', () => {
  it('app-shell renders both navbar and footer', () => {
    mockUseAuth.mockReturnValue({ user: null, logout: vi.fn() });
    render(
      <MemoryRouter>
        <div className="app-shell">
          <Navbar />
          <main className="app-main"><p>Content</p></main>
          <SiteFooter />
        </div>
      </MemoryRouter>,
    );
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });
});

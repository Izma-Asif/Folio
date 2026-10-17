import { Newspaper, Moon, Sun } from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';
import { useTheme } from '@/theme';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  [
    'font-ui text-[13px] tracking-wide uppercase transition-colors',
    isActive
      ? 'text-crimson font-semibold'
      : 'text-ink/70 hover:text-ink dark:text-cream-ink/95 dark:hover:text-cream-ink',
  ].join(' ');

export default function TopNav() {
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-40 border-b border-ink/15 dark:border-cream-ink/15 bg-paper/90 dark:bg-navy/90 backdrop-blur supports-[backdrop-filter]:bg-paper/75 dark:supports-[backdrop-filter]:bg-navy/75">
      <div className="mx-auto max-w-broadsheet px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 group">
            <Newspaper className="h-6 w-6 text-crimson transition-transform group-hover:-rotate-6" />
            <span className="font-display text-2xl font-black tracking-tight text-ink dark:text-cream-ink">
              Folio
            </span>
          </Link>

          <nav className="hidden items-center gap-7 sm:flex">
            <NavLink to="/paper" className={navLinkClass}>
              Today
            </NavLink>
            <NavLink to="/archive" className={navLinkClass}>
              Archive
            </NavLink>
            <NavLink to="/profile" className={navLinkClass}>
              My Interests
            </NavLink>
          </nav>

          <div className="flex items-center gap-3">
            <button
              onClick={toggle}
              aria-label={theme === 'light' ? 'Switch to evening edition' : 'Switch to morning edition'}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-ink/20 text-ink transition-colors hover:bg-ink hover:text-paper dark:border-crimson/50 dark:text-crimson dark:hover:bg-crimson dark:hover:text-paper"
            >
              {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Mobile nav */}
        <nav className="flex items-center justify-center gap-6 pb-2 sm:hidden">
          <NavLink to="/paper" className={navLinkClass}>
            Today
          </NavLink>
          <NavLink to="/archive" className={navLinkClass}>
            Archive
          </NavLink>
          <NavLink to="/profile" className={navLinkClass}>
            Interests
          </NavLink>
        </nav>
      </div>
    </header>
  );
}

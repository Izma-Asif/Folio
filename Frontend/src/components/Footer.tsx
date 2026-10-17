import { Link } from 'react-router-dom';
import { Newspaper } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-ink/15 bg-paper/60 dark:border-cream-ink/15 dark:bg-navy/60">
      <div className="mx-auto max-w-broadsheet px-4 py-10 sm:px-6">
        <div className="rule-double border-ink/70 dark:border-cream-ink/70" />
        <div className="mt-6 flex flex-col items-center justify-between gap-4 sm:flex-row">
          <Link to="/" className="flex items-center gap-2 group">
            <Newspaper className="h-5 w-5 text-crimson transition-transform group-hover:-rotate-6" />
            <span className="font-display text-lg font-black tracking-tight text-ink dark:text-cream-ink">
              Folio
            </span>
          </Link>
          <nav className="flex items-center gap-5" aria-label="Footer">
            <Link
              to="/paper"
              className="font-ui text-xs uppercase tracking-wider text-ink/55 transition-colors hover:text-crimson dark:text-cream-ink"
            >
              Today
            </Link>
            <Link
              to="/archive"
              className="font-ui text-xs uppercase tracking-wider text-ink/55 transition-colors hover:text-crimson dark:text-cream-ink"
            >
              Archive
            </Link>
            <Link
              to="/profile"
              className="font-ui text-xs uppercase tracking-wider text-ink/55 transition-colors hover:text-crimson dark:text-cream-ink"
            >
              My Interests
            </Link>
          </nav>
        </div>
        <p className="mt-5 text-center font-ui text-[11px] uppercase tracking-[0.2em] text-ink/40 dark:text-cream-ink/95">
          Folio — Published every morning, for you
        </p>
      </div>
    </footer>
  );
}

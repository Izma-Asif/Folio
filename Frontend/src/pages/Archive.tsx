import { useEffect, useState } from 'react';
import { Calendar, CloudSun, ArrowRight, AlertCircle, Archive as ArchiveIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Edition } from '@/types';
import { getEditions } from '@/api';
import { ArchiveSkeleton } from '@/components/Skeleton';

function formatPretty(date: string): string {
  return new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export default function Archive() {
  const [editions, setEditions] = useState<Edition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const eds = await getEditions(30);
        if (active) {
          setEditions(eds);
          setLoading(false);
        }
      } catch {
        if (active) {
          setError("We couldn't load the archive stacks. Please try again.");
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <ArchiveSkeleton />;
  }

  if (error) {
    return (
      <div className="paper-texture min-h-[calc(100vh-4rem)]">
        <div className="mx-auto max-w-broadsheet px-4 py-12 sm:px-6">
          <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
            <AlertCircle className="h-10 w-10 text-crimson" />
            <p className="mt-4 font-display text-2xl font-bold text-ink dark:text-cream-ink">
              The stacks are temporarily closed
            </p>
            <p className="mt-2 max-w-sm font-body text-ink/70 dark:text-cream-ink/95">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-5 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (editions.length === 0) {
    return (
      <div className="paper-texture min-h-[calc(100vh-4rem)]">
        <div className="mx-auto max-w-broadsheet px-4 py-12 sm:px-6">
          <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
            <ArchiveIcon className="h-10 w-10 text-crimson" />
            <p className="mt-4 font-display text-2xl font-bold text-ink dark:text-cream-ink">
              The archive is empty
            </p>
            <p className="mt-2 max-w-sm font-body text-ink/70 dark:text-cream-ink/95">
              Build your paper to start collecting daily editions.
            </p>
            <Link
              to="/onboarding"
              className="mt-5 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
            >
              Build my paper →
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="paper-texture min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-broadsheet px-4 py-12 sm:px-6">
        {/* Header */}
        <div className="text-center">
          <p className="font-ui text-xs uppercase tracking-[0.3em] text-crimson">
            The Archive
          </p>
          <h1 className="mt-2 font-display text-5xl font-black tracking-tight text-ink dark:text-cream-ink">
            Past Editions
          </h1>
          <p className="mx-auto mt-3 max-w-md font-body text-base text-ink/65 dark:text-cream-ink/95">
            Every morning we've printed for you, folded and filed newest first.
          </p>
          <div className="mx-auto mt-5 max-w-xs rule-double border-ink/70 dark:border-cream-ink/70" />
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {editions.map((ed, idx) => (
            <EditionCard key={ed.id} edition={ed} index={idx} />
          ))}
        </div>
      </div>
    </div>
  );
}

function EditionCard({ edition, index }: { edition: Edition; index: number }) {
  const lead = edition.stories.find((s) => s.kind === 'lead');
  const standards = edition.stories.filter((s) => s.kind === 'standard');
  const briefs = edition.stories.filter((s) => s.kind === 'brief');
  const storyCount = edition.stories.length;

  return (
    <Link
      to={`/paper/${edition.id}`}
      className="group relative block animate-fade-up"
      style={{ animationDelay: `${Math.min(index * 40, 400)}ms` }}
    >
      {/* Paper shadow stack */}
      <div className="absolute inset-0 translate-x-1 translate-y-1 rounded-sm border border-ink/8 bg-ink/5 dark:border-cream-ink/8 dark:bg-cream-ink/5" />

      <div className="paper-grain relative rounded-sm border border-ink/20 bg-paper/95 p-4 transition-all duration-200 group-hover:-translate-y-1 group-hover:shadow-paper dark:border-cream-ink/15 dark:bg-navy-2/90">
        {/* Mini masthead */}
        <div className="text-center">
          <div className="flex items-center justify-between font-ui text-[9px] uppercase tracking-[0.15em] text-ink/45 dark:text-cream-ink/95">
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-2.5 w-2.5" />
              {formatPretty(edition.date)}
            </span>
            <span className="inline-flex items-center gap-1">
              <CloudSun className="h-2.5 w-2.5" />
              {edition.weather.temp}°
            </span>
          </div>
          <h2 className="mt-0.5 font-display text-xl font-black tracking-tight text-ink dark:text-cream-ink">
            Folio
          </h2>
        </div>

        <div className="my-2 rule-double border-ink/60 dark:border-cream-ink/60" />

        {/* Lead headline */}
        <article>
          <p className="font-ui text-[9px] font-semibold uppercase tracking-[0.2em] text-crimson">
            {lead?.section ?? 'Front Page'}
          </p>
          <h3 className="mt-1 font-display text-base font-black leading-[1.15] text-ink transition-colors group-hover:text-crimson dark:text-cream-ink">
            {lead?.headline ?? edition.headline}
          </h3>
          <p className="mt-1 line-clamp-2 font-body text-xs leading-relaxed text-ink/65 dark:text-cream-ink/95">
            {lead?.dek}
          </p>
        </article>

        <div className="my-2 rule-thin border-ink/15 dark:border-cream-ink/15" />

        {/* Mini column stories */}
        <div className="grid grid-cols-2 gap-2">
          {standards.slice(0, 2).map((s, i) => (
            <article
              key={s.id}
              className={i > 0 ? 'border-l border-ink/10 pl-2 dark:border-cream-ink/10' : ''}
            >
              <p className="font-ui text-[8px] font-semibold uppercase tracking-[0.15em] text-crimson">
                {s.section}
              </p>
              <h4 className="mt-0.5 font-display text-[11px] font-bold leading-tight text-ink dark:text-cream-ink">
                {s.headline}
              </h4>
            </article>
          ))}
        </div>

        {/* Briefs as tiny lines */}
        {briefs.length > 0 && (
          <>
            <div className="my-2 rule-thin border-ink/10 dark:border-cream-ink/10" />
            <div className="space-y-0.5">
              {briefs.slice(0, 2).map((b) => (
                <p key={b.id} className="font-body text-[10px] leading-tight text-ink/55 dark:text-cream-ink">
                  · {b.headline}
                </p>
              ))}
            </div>
          </>
        )}

        <div className="mt-2 rule-thin border-ink/10 dark:border-cream-ink/10" />

        {/* Footer */}
        <div className="flex items-center justify-between pt-1.5">
          <span className="font-ui text-[9px] uppercase tracking-wider text-ink/40 dark:text-cream-ink/95">
            {storyCount} stories
          </span>
          <span className="inline-flex items-center gap-1 font-ui text-[9px] uppercase tracking-wider text-crimson opacity-0 transition-opacity group-hover:opacity-100">
            Read
            <ArrowRight className="h-2.5 w-2.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}

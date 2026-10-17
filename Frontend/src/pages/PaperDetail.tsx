import { useEffect, useState } from 'react';
import { ArrowLeft, Calendar, CloudSun, AlertCircle } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import type { Edition } from '@/types';
import { getEdition } from '@/api';
import Masthead from '@/components/Masthead';
import StoryCard from '@/components/StoryCard';
import { PaperSkeleton } from '@/components/Skeleton';

export default function PaperDetail() {
  const { id } = useParams<{ id: string }>();
  const [edition, setEdition] = useState<Edition | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setNotFound(false);
      setError(null);
      try {
        const ed = id ? await getEdition(id) : null;
        if (active) {
          setEdition(ed);
          setNotFound(!ed);
          setLoading(false);
        }
      } catch {
        if (active) {
          setError("We couldn't retrieve that edition from the archives.");
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [id]);

  if (loading) {
    return <PaperSkeleton />;
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4 text-center">
        <div>
          <AlertCircle className="mx-auto h-10 w-10 text-crimson" />
          <p className="mt-4 font-display text-2xl font-bold text-ink dark:text-cream-ink">
            Archive error
          </p>
          <p className="mt-2 max-w-sm font-body text-ink/70 dark:text-cream-ink/95">{error}</p>
          <Link
            to="/archive"
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to archive
          </Link>
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4 text-center">
        <div>
          <p className="font-display text-2xl font-bold text-ink dark:text-cream-ink">
            That edition is not in the archives
          </p>
          <p className="mt-2 max-w-sm font-body text-ink/60 dark:text-cream-ink/95">
            It may have been from a date before your subscription started.
          </p>
          <Link
            to="/archive"
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to the archive
          </Link>
        </div>
      </div>
    );
  }

  if (!edition) return null;

  const lead = edition.stories.find((s) => s.kind === 'lead') ?? edition.stories[0];
  const standards = edition.stories.filter((s) => s.kind === 'standard');
  const opinion = edition.stories.find((s) => s.kind === 'opinion');
  const briefs = edition.stories.filter((s) => s.kind === 'brief');

  return (
    <div className="paper-texture pb-20">
      <div className="mx-auto max-w-broadsheet px-4 py-10 sm:px-6">
        <Link
          to="/archive"
          className="no-print inline-flex items-center gap-2 font-ui text-xs uppercase tracking-wider text-ink/60 transition-colors hover:text-crimson dark:text-cream-ink/95"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to archive
        </Link>

        <div className="mt-6">
          <Masthead edition={edition} editionLabel="From the Archive" />
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-4 font-ui text-sm text-ink/70 dark:text-cream-ink/95">
          <span className="inline-flex items-center gap-1.5">
            <Calendar className="h-4 w-4 text-crimson" />
            {edition.date}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CloudSun className="h-4 w-4 text-crimson" />
            {edition.weather.temp}°F · {edition.weather.condition}
          </span>
        </div>

        <div className="mx-auto mt-6 max-w-md rule-double border-ink/80 dark:border-cream-ink/80" />

        <div className="mt-8">
          <StoryCard story={lead} variant="lead" />
        </div>

        <div className="my-10 rule-double border-ink/80 dark:border-cream-ink/80" />

        <div className="grid gap-10 md:grid-cols-2 md:gap-x-12 md:gap-y-10">
          {standards.map((s) => (
            <StoryCard key={s.id} story={s} variant="standard" />
          ))}
        </div>

        <div className="my-10 rule-thin border-ink/20 dark:border-cream-ink/20" />

        <div className="grid gap-10 md:grid-cols-3">
          <div className="md:col-span-1">
            <h3 className="font-display text-xl font-black uppercase tracking-tight text-ink dark:text-cream-ink">
              In Brief
            </h3>
            <div className="mt-3 divide-y divide-ink/15 dark:divide-cream-ink/15">
              {briefs.map((b) => (
                <StoryCard key={b.id} story={b} variant="brief" />
              ))}
            </div>
          </div>
          <div className="md:col-span-2">
            {opinion && <StoryCard story={opinion} variant="opinion" />}
          </div>
        </div>
      </div>
    </div>
  );
}

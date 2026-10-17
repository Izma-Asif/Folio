import type { Edition } from '@/types';

function formatDate(date: string): string {
  const d = new Date(date + 'T00:00:00');
  return d.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export default function Masthead({
  edition,
  editionLabel = 'The Morning Edition',
}: {
  edition: Edition;
  editionLabel?: string;
}) {
  return (
    <div className="text-center">
      <p className="font-ui text-[11px] uppercase tracking-[0.25em] text-ink/60 dark:text-cream-ink/95">
        {editionLabel}
      </p>
      <h1 className="mt-1 font-display text-4xl font-black tracking-tight text-ink dark:text-cream-ink sm:text-5xl">
        Folio
      </h1>
      <p className="mt-1 font-ui text-xs text-ink/70 dark:text-cream-ink/95">
        {formatDate(edition.date)}
      </p>
      <div className="mx-auto mt-4 max-w-md rule-double border-ink/80 dark:border-cream-ink/80" />
    </div>
  );
}

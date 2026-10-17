import type { Story } from '@/types';

function readingTimeLabel(min: number): string {
  return `${min} min read`;
}

export default function StoryCard({
  story,
  variant = 'standard',
}: {
  story: Story;
  variant?: 'lead' | 'standard' | 'brief' | 'opinion';
}) {
  if (variant === 'lead') {
    return (
      <article className="animate-fade-up">
        <p className="font-ui text-[11px] font-semibold uppercase tracking-[0.2em] text-crimson">
          {story.section}
        </p>
        <h2 className="mt-2 font-display text-3xl font-black leading-[1.1] text-ink dark:text-cream-ink sm:text-4xl md:text-5xl">
          {story.headline}
        </h2>
        <p className="mt-3 font-body text-lg leading-relaxed text-ink/80 dark:text-cream-ink">
          {story.dek}
        </p>
        <p className="mt-3 font-ui text-xs uppercase tracking-wider text-ink/55 dark:text-cream-ink">
          {story.byline} · {readingTimeLabel(story.readingTime)}
        </p>
        <div className="mt-4 max-w-2xl space-y-4 font-body text-[17px] leading-[1.7] text-ink/90 dark:text-cream-ink">
          <p className="dropcap">{story.body[0]}</p>
          {story.body.slice(1).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </article>
    );
  }

  if (variant === 'brief') {
    return (
      <article className="py-3 first:pt-0">
        <h4 className="font-display text-base font-bold leading-snug text-ink dark:text-cream-ink">
          {story.headline}
        </h4>
        <p className="mt-1 font-body text-sm leading-relaxed text-ink/75 dark:text-cream-ink/95">
          {story.body[0]}
        </p>
      </article>
    );
  }

  if (variant === 'opinion') {
    return (
      <article className="animate-fade-up border-l-4 border-crimson pl-5">
        <p className="font-ui text-[11px] font-semibold uppercase tracking-[0.2em] text-crimson">
          {story.section}
        </p>
        <h3 className="mt-2 font-display text-2xl font-bold italic leading-tight text-ink dark:text-cream-ink">
          {story.headline}
        </h3>
        <p className="mt-2 font-body text-base italic text-ink/80 dark:text-cream-ink">
          {story.dek}
        </p>
        <p className="mt-3 font-ui text-xs uppercase tracking-wider text-ink/55 dark:text-cream-ink">
          {story.byline} · {readingTimeLabel(story.readingTime)}
        </p>
        <div className="mt-3 space-y-3 font-body text-[16px] leading-[1.7] text-ink/90 dark:text-cream-ink">
          {story.body.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </article>
    );
  }

  // standard
  return (
    <article className="animate-fade-up">
      <p className="font-ui text-[11px] font-semibold uppercase tracking-[0.2em] text-crimson">
        {story.section}
      </p>
      <h3 className="mt-2 font-display text-2xl font-bold leading-tight text-ink dark:text-cream-ink">
        {story.headline}
      </h3>
      <p className="mt-2 font-body text-base leading-relaxed text-ink/80 dark:text-cream-ink">
        {story.dek}
      </p>
      <p className="mt-2 font-ui text-xs uppercase tracking-wider text-ink/55 dark:text-cream-ink">
        {story.byline} · {readingTimeLabel(story.readingTime)}
      </p>
      <div className="mt-3 space-y-3 font-body text-[16px] leading-[1.7] text-ink/90 dark:text-cream-ink">
        {story.body.slice(0, 1).map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      <button className="mt-2 font-ui text-xs font-semibold uppercase tracking-wider text-crimson hover:underline">
        Continue reading →
      </button>
    </article>
  );
}

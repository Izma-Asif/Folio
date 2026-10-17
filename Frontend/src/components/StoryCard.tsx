import { useState } from 'react';
import { Bookmark, ExternalLink, X } from 'lucide-react';
import type { Story } from '@/types';
import { trackEvent } from '@/api';

function readingTimeLabel(min: number): string {
  return `${min} min read`;
}

function StoryImage({
  src,
  label,
  tall = false,
  fallback = false,
  className = '',
}: {
  src?: string;
  label: string;
  tall?: boolean;
  fallback?: boolean;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    if (!fallback) return null;
    return (
      <div
        className={`flex items-end border-t-4 border-crimson bg-ink/5 p-4 dark:bg-cream-ink/10 ${
          tall ? 'h-48 sm:h-64' : 'h-28'
        } ${className}`}
      >
        <span className="font-ui text-[11px] font-semibold uppercase tracking-[0.2em] text-crimson">
          {label}
        </span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`w-full rounded-sm object-cover ${tall ? 'h-56 sm:h-80' : 'h-40'} ${className}`}
    />
  );
}

export default function StoryCard({
  story,
  variant = 'standard',
  showImages = true,
}: {
  story: Story;
  variant?: 'lead' | 'standard' | 'brief' | 'opinion';
  showImages?: boolean;
}) {
  const [hidden, setHidden] = useState(false);
  const [saved, setSaved] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const track = (type: string, reason?: string) => {
    void trackEvent({ type, storyId: story.id, articleId: story.id, reason } as any);
  };

  if (hidden) return null;

  const actions = (
    <div className="no-print mt-3 flex flex-wrap items-center gap-4 font-ui text-xs uppercase tracking-wider">
      {story.link && (
        <a
          href={story.link}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => track('click')}
          className="inline-flex items-center gap-1 font-semibold text-crimson hover:underline"
        >
          Read original <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
      <button
        onClick={() => {
          if (!saved) {
            track('save');
            setSaved(true);
          }
        }}
        className={`inline-flex items-center gap-1 ${
          saved ? 'font-semibold text-crimson' : 'text-ink/60 hover:text-ink dark:text-cream-ink/95 dark:hover:text-cream-ink'
        }`}
      >
        <Bookmark className={`h-3.5 w-3.5 ${saved ? 'fill-current' : ''}`} />
        {saved ? 'Saved' : 'Save'}
      </button>
      <div className="relative">
        <button
          onClick={() => setMenuOpen((o) => !o)}
          className="inline-flex items-center gap-1 text-ink/60 hover:text-ink dark:text-cream-ink/95 dark:hover:text-cream-ink"
        >
          <X className="h-3.5 w-3.5" />
          Skip
        </button>
        {menuOpen && (
          <div className="absolute z-10 mt-1 w-48 rounded-md border border-ink/20 bg-paper p-1 shadow-lg dark:border-cream-ink/20 dark:bg-navy-2">
            {[
              ['Not interested', 'not_interested'],
              ['Already know this', 'already_know'],
              ['Too negative', 'too_negative'],
            ].map(([label, reason]) => (
              <button
                key={reason}
                onClick={() => {
                  track('skip', reason);
                  setHidden(true);
                }}
                className="block w-full rounded px-3 py-2 text-left font-ui text-xs normal-case tracking-normal text-ink hover:bg-ink/5 dark:text-cream-ink dark:hover:bg-cream-ink/10"
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );

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
        {showImages && (
          <StoryImage src={story.imageUrl} label={story.section} tall fallback className="mt-4" />
        )}
        <div className="mt-4 max-w-2xl space-y-4 font-body text-[17px] leading-[1.7] text-ink/90 dark:text-cream-ink">
          <p className="dropcap">{story.body[0]}</p>
          {story.body.slice(1).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
        {actions}
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
        {actions}
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
        {actions}
      </article>
    );
  }

  // standard
  return (
    <article className="animate-fade-up">
      {showImages && <StoryImage src={story.imageUrl} label={story.section} className="mb-3" />}
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
      {actions}
    </article>
  );
}
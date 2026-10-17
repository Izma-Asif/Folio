import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';

function todayLabel(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export default function Landing() {
  return (
    <div className="paper-texture relative overflow-hidden">
      {/* Halftone background behind hero */}
      <div className="halftone pointer-events-none absolute inset-0 opacity-60" aria-hidden />

      {/* Hero */}
      <section className="relative mx-auto max-w-broadsheet px-4 pb-16 pt-12 sm:px-6 sm:pt-20 lg:pt-28">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
          {/* Left column */}
          <div className="animate-fade-up">
            <p className="font-ui text-xs font-semibold uppercase tracking-[0.3em] text-crimson">
              A personalized morning newspaper
            </p>
            <h1 className="mt-5 max-w-xl font-display text-5xl font-black leading-[0.98] tracking-tight text-ink dark:text-cream-ink sm:text-6xl lg:text-7xl">
              Your morning,
              <br />
              edited.
            </h1>
            <p className="mt-6 max-w-md font-body text-lg leading-relaxed text-ink/75 dark:text-cream-ink">
              One personal paper. Made for you. Finished in 10 minutes.
            </p>
            <div className="mt-8 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
              <Link
                to="/onboarding"
                className="inline-flex items-center gap-2 rounded-full bg-crimson px-7 py-3.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
              >
                Build my paper
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/paper"
                className="inline-flex items-center gap-1 font-ui text-sm font-semibold uppercase tracking-wider text-crimson underline-offset-4 hover:underline"
              >
                See a sample
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {/* Right column: CSS newspaper illustration */}
          <div className="animate-fade-up [animation-delay:120ms]">
            <NewspaperIllustration />
          </div>
        </div>
      </section>

      {/* Double rule divider */}
      <div className="mx-auto max-w-broadsheet px-4 sm:px-6">
        <div className="rule-double border-ink/70 dark:border-cream-ink/70" />
      </div>

      {/* Closing strip */}
      <section className="mx-auto max-w-broadsheet px-4 py-14 sm:px-6">
        <div className="grid gap-10 md:grid-cols-3">
          <Pillar n="01" title="Curated to you" body="We infer your interests and weight each section accordingly. The front page is yours alone." />
          <Pillar n="02" title="Set in type" body="Headlines, decks, bylines, and briefs — the grammar of a real newspaper, applied to a personal feed." />
          <Pillar n="03" title="A morning ritual" body="One edition a day. No infinite scroll, no refreshing. Read it, then go live your day." />
        </div>
        <div className="mt-12 text-center">
          <Link
            to="/onboarding"
            className="inline-flex items-center gap-2 rounded-full bg-crimson px-7 py-3.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
          >
            Build my paper
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}

function NewspaperIllustration() {
  return (
    <div className="relative mx-auto max-w-sm">
      {/* Paper shadow stack behind */}
      <div className="absolute inset-0 translate-x-1.5 translate-y-1.5 rounded-sm border border-ink/10 bg-ink/5 dark:border-cream-ink/10 dark:bg-cream-ink/5" />
      <div className="absolute inset-0 translate-x-0.5 translate-y-0.5 rounded-sm border border-ink/10 bg-ink/3 dark:border-cream-ink/10 dark:bg-cream-ink/3" />

      {/* Main paper */}
      <div className="paper-grain relative rounded-sm border border-ink/25 bg-paper/95 p-5 shadow-paper dark:border-cream-ink/20 dark:bg-navy-2/90 sm:p-6">
        {/* Masthead */}
        <div className="text-center">
          <div className="flex items-center justify-between font-ui text-[10px] uppercase tracking-[0.2em] text-ink/45 dark:text-cream-ink/95">
            <span>{new Date().getFullYear()}</span>
            <span>Vol. 1 · No. 1</span>
            <span>{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
          </div>
          <h2 className="mt-1 font-display text-4xl font-black tracking-tight text-ink dark:text-cream-ink">
            Folio
          </h2>
          <p className="font-ui text-[10px] uppercase tracking-[0.15em] text-ink/45 dark:text-cream-ink/95">
            {todayLabel()}
          </p>
        </div>

        <div className="my-3 rule-double border-ink/70 dark:border-cream-ink/70" />

        {/* Lead story */}
        <article>
          <p className="font-ui text-[10px] font-semibold uppercase tracking-[0.2em] text-crimson">
            The Frontier
          </p>
          <h3 className="mt-1.5 font-display text-2xl font-black leading-[1.12] text-ink dark:text-cream-ink">
            A Breakthrough in Patient, Deliberate Reasoning
          </h3>
          <p className="mt-1.5 font-body text-sm leading-relaxed text-ink/75 dark:text-cream-ink">
            Researchers report steady gains from longer deliberation, reshaping the morning
            conversation about what machines can do.
          </p>
        </article>

        <div className="my-3 rule-thin border-ink/20 dark:border-cream-ink/20" />

        {/* Three stories in columns */}
        <div className="grid grid-cols-1 gap-0 sm:grid-cols-3">
          <article className="py-2 sm:pr-3">
            <p className="font-ui text-[9px] font-semibold uppercase tracking-[0.2em] text-crimson">
              Markets
            </p>
            <h4 className="mt-1 font-display text-sm font-bold leading-snug text-ink dark:text-cream-ink">
              Rally Holds as Earnings Defy Forecast
            </h4>
            <p className="mt-1 font-body text-xs leading-relaxed text-ink/70 dark:text-cream-ink/95">
              The index closed at a three-month high after a week of steady buying.
            </p>
          </article>
          <article className="py-2 sm:border-l sm:border-ink/15 sm:px-3 dark:border-cream-ink/15">
            <p className="font-ui text-[9px] font-semibold uppercase tracking-[0.2em] text-crimson">
              Science
            </p>
            <h4 className="mt-1 font-display text-sm font-bold leading-snug text-ink dark:text-cream-ink">
              Telescope Captures Faint Distant Signal
            </h4>
            <p className="mt-1 font-body text-xs leading-relaxed text-ink/70 dark:text-cream-ink/95">
              The observation pushes estimates of early star formation back by millions of years.
            </p>
          </article>
          <article className="py-2 sm:border-l sm:border-ink/15 sm:pl-3 dark:border-cream-ink/15">
            <p className="font-ui text-[9px] font-semibold uppercase tracking-[0.2em] text-crimson">
              Culture
            </p>
            <h4 className="mt-1 font-display text-sm font-bold leading-snug text-ink dark:text-cream-ink">
              A Sold-Out Run Brings a Play Back
            </h4>
            <p className="mt-1 font-body text-xs leading-relaxed text-ink/70 dark:text-cream-ink/95">
              The revival trades grandeur for intimacy, and the trade pays off.
            </p>
          </article>
        </div>

        <div className="mt-2 rule-thin border-ink/15 dark:border-cream-ink/15" />
        <p className="mt-2 text-center font-ui text-[9px] uppercase tracking-[0.2em] text-ink/40 dark:text-cream-ink/95">
          Printed every morning · for you
        </p>
      </div>
    </div>
  );
}

function Pillar({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="relative pl-12">
      <span className="absolute left-0 top-0 font-display text-2xl font-black text-crimson/70">
        {n}
      </span>
      <h3 className="font-display text-xl font-bold text-ink dark:text-cream-ink">{title}</h3>
      <p className="mt-2 max-w-xs font-body text-base leading-relaxed text-ink/70 dark:text-cream-ink/95">
        {body}
      </p>
    </div>
  );
}

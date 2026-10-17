import { useMemo, useState } from 'react';
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Sparkles,
  Eye,
  BookOpen,
  Printer,
  Link2,
  Globe,
  Languages,
  PenLine,
  Rss,
  Flag,
  Landmark,
  Briefcase,
  Cpu,
  BrainCircuit,
  Dumbbell,
  CircleDot,
  FlaskConical,
  HeartPulse,
  Clapperboard,
  Palette,
  CloudRain,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { createUser, inferInterests, listAllInterests } from '@/api';
import type { Language, VisualMode } from '@/types';

const STORAGE_KEY = 'folio_user_id';

export default function Onboarding() {
  const navigate = useNavigate();
  const allInterests = useMemo(() => listAllInterests(), []);

  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [links, setLinks] = useState('');
  const [inferring, setInferring] = useState(false);
  const [inferred, setInferred] = useState<string[] | null>(null);
  const [inferError, setInferError] = useState<string | null>(null);

  const [visualMode, setVisualMode] = useState<VisualMode>('visual');
  const [calmMode, setCalmMode] = useState(false);

  const [language, setLanguage] = useState<Language>('en');

  const [editorNote, setEditorNote] = useState('');
  const [rssFeed, setRssFeed] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleInterest = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
    setInferred(null);
  };

  const canProceedStep0 = selected.length >= 3;

  const handleLearn = async () => {
    setInferring(true);
    setInferError(null);
    try {
      const sources = links
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean);
      const result = await inferInterests({ topics: selected, sources });
      setInferred(result);
      setSelected(Array.from(new Set([...selected, ...result])));
    } catch {
      setInferError('Could not analyze those links right now. Pick a few manually.');
    } finally {
      setInferring(false);
    }
  };

  const handleFinish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const customFeeds = rssFeed.trim()
        ? [rssFeed.trim()]
        : links
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean);

      const user = await createUser({
        interests: selected,
        custom_feeds: customFeeds,
        language,
        calm_mode: calmMode,
        visual_mode: visualMode,
      });
      window.localStorage.setItem(STORAGE_KEY, user.id);
      navigate('/paper');
    } catch {
      setError('Something went wrong printing your edition. Try again.');
      setSubmitting(false);
    }
  };

  const steps = ['Interests', 'Style', 'Language', 'Finish'];

  return (
    <div className="paper-texture min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6 sm:py-14">
        {/* Progress bar */}
        <div className="mb-10">
          <div className="flex items-center justify-between">
            {steps.map((label, i) => (
              <div key={label} className="flex flex-1 items-center last:flex-none">
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full border-2 font-ui text-xs font-bold transition-all duration-300 ${
                      i < step
                        ? 'border-crimson bg-crimson text-paper'
                        : i === step
                          ? 'border-crimson text-crimson'
                          : 'border-ink/20 text-ink/40 dark:border-cream-ink/20 dark:text-cream-ink/95'
                    }`}
                  >
                    {i < step ? <Check className="h-4 w-4" /> : i + 1}
                  </div>
                  <span
                    className={`font-ui text-[10px] uppercase tracking-wider transition-colors ${
                      i <= step
                        ? 'text-ink dark:text-cream-ink'
                        : 'text-ink/40 dark:text-cream-ink/95'
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div className="mx-2 h-0.5 flex-1 rounded-full transition-colors duration-500 sm:mx-3"
                    style={{ backgroundColor: i < step ? 'var(--tw-color, #1F3A5F)' : 'rgba(22,24,29,0.12)' }}
                  >
                    <div
                      className={`h-full rounded-full bg-crimson transition-all duration-500 ${
                        i < step ? 'w-full' : 'w-0'
                      }`}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step 0: Interests */}
        {step === 0 && (
          <section className="animate-fade-up">
            <h1 className="font-display text-3xl font-black text-ink dark:text-cream-ink">
              What do you care about?
            </h1>
            <p className="mt-2 font-body text-base text-ink/70 dark:text-cream-ink/95">
              Pick at least three topics. You can change these any time.
            </p>
            <p className="mt-1 font-ui text-xs uppercase tracking-wider text-ink/50 dark:text-cream-ink/95">
              {selected.length} selected
            </p>

            <div className="mt-6 flex flex-wrap gap-2.5">
              {allInterests.map((interest) => {
                const active = selected.includes(interest.id);
                const Icon = iconMap[interest.icon] ?? Globe;
                return (
                  <button
                    key={interest.id}
                    onClick={() => toggleInterest(interest.id)}
                    className={`inline-flex items-center gap-2 rounded-full border px-4 py-2.5 font-ui text-sm transition-all ${
                      active
                        ? 'border-crimson bg-crimson text-paper'
                        : 'border-ink/25 text-ink hover:border-crimson hover:text-crimson dark:border-cream-ink/25 dark:text-cream-ink dark:hover:border-crimson dark:hover:text-crimson'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {interest.label}
                    {active && <Check className="h-3.5 w-3.5" />}
                  </button>
                );
              })}
            </div>

            {/* Optional: paste links */}
            <div className="mt-8 rounded-lg border border-ink/15 p-5 dark:border-cream-ink/15">
              <label className="block">
                <span className="inline-flex items-center gap-2 font-ui text-xs font-semibold uppercase tracking-wider text-ink/60 dark:text-cream-ink/95">
                  <Link2 className="h-3.5 w-3.5" />
                  Or paste links to articles or channels you read
                </span>
                <textarea
                  value={links}
                  onChange={(e) => setLinks(e.target.value)}
                  rows={3}
                  placeholder="https://example.com/feed&#10;https://youtube.com/@channel"
                  className="mt-2 w-full resize-none rounded-md border border-ink/20 bg-paper/50 p-3 font-body text-sm text-ink outline-none transition-colors focus:border-crimson dark:border-crimson/40 dark:bg-navy-2/40 dark:text-cream-ink"
                />
              </label>
              <button
                onClick={handleLearn}
                disabled={inferring || (!links.trim() && selected.length === 0)}
                className="mt-3 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all disabled:opacity-40 enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
              >
                <Sparkles className="h-4 w-4" />
                {inferring ? 'Learning…' : 'Learn from these'}
              </button>

              {inferError && (
                <p className="mt-3 font-ui text-sm text-crimson">{inferError}</p>
              )}

              {/* Inferred card */}
              {inferred && inferred.length > 0 && (
                <div className="mt-4 animate-fade-up rounded-md border border-crimson/30 bg-crimson/5 p-4 dark:border-crimson/40 dark:bg-crimson/10">
                  <p className="font-ui text-xs font-semibold uppercase tracking-wider text-crimson">
                    Here's what I learned about you:
                  </p>
                  <p className="mt-1.5 font-body text-sm text-ink/80 dark:text-cream-ink/95">
                    Based on what you shared, I think you'd like these topics. They're now
                    pre-selected — feel free to remove any that don't fit.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {inferred.map((id) => {
                      const interest = allInterests.find((i) => i.id === id);
                      const Icon = interest ? iconMap[interest.icon] ?? Globe : Globe;
                      return (
                        <span
                          key={id}
                          className="inline-flex items-center gap-1.5 rounded-full border border-crimson/40 px-3 py-1.5 font-ui text-xs font-medium text-crimson"
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {interest?.label ?? id}
                          <button
                            onClick={() => toggleInterest(id)}
                            className="ml-1 text-crimson/60 hover:text-crimson"
                            aria-label={`Remove ${interest?.label ?? id}`}
                          >
                            ×
                          </button>
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {error && <p className="mt-4 font-ui text-sm text-crimson">{error}</p>}

            <div className="mt-10 flex justify-end">
              <button
                disabled={!canProceedStep0}
                onClick={() => setStep(1)}
                className="inline-flex items-center gap-2 rounded-full bg-crimson px-6 py-3 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all disabled:opacity-40 enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
              >
                Continue
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* Step 1: Style */}
        {step === 1 && (
          <section className="animate-fade-up">
            <h1 className="font-display text-3xl font-black text-ink dark:text-cream-ink">
              How do you like your paper?
            </h1>
            <p className="mt-2 font-body text-base text-ink/70 dark:text-cream-ink/95">
              Choose a reading style. You can switch later.
            </p>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <StyleCard
                active={visualMode === 'visual'}
                onClick={() => setVisualMode('visual')}
                icon={<Eye className="h-6 w-6" />}
                title="Visual"
                body="Photos, illustrations, and a richly designed layout. A paper you can linger over."
              />
              <StyleCard
                active={visualMode === 'reader'}
                onClick={() => setVisualMode('reader')}
                icon={<BookOpen className="h-6 w-6" />}
                title="Reader"
                body="Text-first and distraction-free. Clean columns, generous spacing, no clutter."
              />
            </div>

            {/* Calm mode toggle */}
            <div className="mt-6 flex items-center justify-between rounded-lg border border-ink/15 p-4 dark:border-cream-ink/15">
              <div>
                <p className="font-ui text-sm font-semibold text-ink dark:text-cream-ink">
                  Calm mode
                </p>
                <p className="mt-0.5 font-body text-sm text-ink/60 dark:text-cream-ink/95">
                  Fewer distressing stories. We'll soften the front page.
                </p>
              </div>
              <Toggle on={calmMode} onChange={setCalmMode} />
            </div>

            <div className="mt-10 flex items-center justify-between">
              <button
                onClick={() => setStep(0)}
                className="inline-flex items-center gap-2 font-ui text-sm font-semibold uppercase tracking-wider text-ink/60 hover:text-ink dark:text-cream-ink/95 dark:hover:text-cream-ink"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>
              <button
                onClick={() => setStep(2)}
                className="inline-flex items-center gap-2 rounded-full bg-crimson px-6 py-3 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
              >
                Continue
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* Step 2: Language */}
        {step === 2 && (
          <section className="animate-fade-up">
            <h1 className="font-display text-3xl font-black text-ink dark:text-cream-ink">
              Language
            </h1>
            <p className="mt-2 font-body text-base text-ink/70 dark:text-cream-ink/95">
              Which language should your paper be in?
            </p>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <LanguageCard
                active={language === 'en'}
                onClick={() => setLanguage('en')}
                label="English"
                sub="Read your morning paper in English."
              />
              <LanguageCard
                active={language === 'ur'}
                onClick={() => setLanguage('ur')}
                label="اردو"
                sub="Urdu edition (label only for now)."
              />
            </div>

            <p className="mt-4 inline-flex items-center gap-1.5 font-ui text-xs uppercase tracking-wider text-ink/40 dark:text-cream-ink/95">
              <Languages className="h-3.5 w-3.5" />
              More languages coming soon
            </p>

            <div className="mt-10 flex items-center justify-between">
              <button
                onClick={() => setStep(1)}
                className="inline-flex items-center gap-2 font-ui text-sm font-semibold uppercase tracking-wider text-ink/60 hover:text-ink dark:text-cream-ink/95 dark:hover:text-cream-ink"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>
              <button
                onClick={() => setStep(3)}
                className="inline-flex items-center gap-2 rounded-full bg-crimson px-6 py-3 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
              >
                Continue
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* Step 3: Anything else? */}
        {step === 3 && (
          <section className="animate-fade-up">
            <h1 className="font-display text-3xl font-black text-ink dark:text-cream-ink">
              Anything else?
            </h1>
            <p className="mt-2 font-body text-base text-ink/70 dark:text-cream-ink/95">
              Last words for your editor before we go to press.
            </p>

            {/* Editor note */}
            <div className="mt-8">
              <label className="block">
                <span className="inline-flex items-center gap-2 font-ui text-xs font-semibold uppercase tracking-wider text-ink/60 dark:text-cream-ink/95">
                  <PenLine className="h-3.5 w-3.5" />
                  Tell your editor
                </span>
                <input
                  value={editorNote}
                  onChange={(e) => setEditorNote(e.target.value)}
                  placeholder="e.g. less politics, more startups"
                  className="mt-2 w-full rounded-md border border-ink/20 bg-paper/50 px-4 py-3 font-body text-sm text-ink outline-none transition-colors focus:border-crimson dark:border-crimson/40 dark:bg-navy-2/40 dark:text-cream-ink"
                />
              </label>
            </div>

            {/* RSS feed */}
            <div className="mt-5">
              <label className="block">
                <span className="inline-flex items-center gap-2 font-ui text-xs font-semibold uppercase tracking-wider text-ink/60 dark:text-cream-ink/95">
                  <Rss className="h-3.5 w-3.5" />
                  Add your own RSS feed link
                </span>
                <input
                  value={rssFeed}
                  onChange={(e) => setRssFeed(e.target.value)}
                  placeholder="https://example.com/rss.xml"
                  className="mt-2 w-full rounded-md border border-ink/20 bg-paper/50 px-4 py-3 font-body text-sm text-ink outline-none transition-colors focus:border-crimson dark:border-crimson/40 dark:bg-navy-2/40 dark:text-cream-ink"
                />
              </label>
            </div>

            {/* Summary */}
            <div className="mt-8 rounded-lg border border-ink/15 p-5 dark:border-cream-ink/15">
              <p className="font-ui text-xs uppercase tracking-wider text-ink/50 dark:text-cream-ink/95">
                Your paper will include
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {selected.map((id) => {
                  const interest = allInterests.find((i) => i.id === id);
                  return (
                    <span
                      key={id}
                      className="rounded-full bg-ink/5 px-3 py-1 font-ui text-xs text-ink dark:bg-cream-ink/10 dark:text-cream-ink"
                    >
                      {interest?.label ?? id}
                    </span>
                  );
                })}
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-ui text-xs text-ink/60 dark:text-cream-ink/95">
                <span>Style: {visualMode === 'visual' ? 'Visual' : 'Reader'}</span>
                <span>Calm mode: {calmMode ? 'On' : 'Off'}</span>
                <span>Language: {language === 'en' ? 'English' : 'اردو'}</span>
              </div>
            </div>

            {error && <p className="mt-4 font-ui text-sm text-crimson">{error}</p>}

            <div className="mt-10 flex items-center justify-between">
              <button
                onClick={() => setStep(2)}
                disabled={submitting}
                className="inline-flex items-center gap-2 font-ui text-sm font-semibold uppercase tracking-wider text-ink/60 hover:text-ink disabled:opacity-50 dark:text-cream-ink/95 dark:hover:text-cream-ink"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>

              {submitting ? (
                <PrintingAnimation />
              ) : (
                <button
                  onClick={handleFinish}
                  className="inline-flex items-center gap-2 rounded-full bg-crimson px-6 py-3 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
                >
                  <Printer className="h-4 w-4" />
                  Print my first edition
                </button>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

// ---------- Icon map ----------

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Flag,
  Globe,
  Landmark,
  Briefcase,
  Cpu,
  BrainCircuit,
  Dumbbell,
  CircleDot,
  FlaskConical,
  HeartPulse,
  Clapperboard,
  Palette,
  CloudRain,
};

// (Populated inline above — no need for separate assignment statements.)

// Unused: keep the line below to avoid dead code lint on iconMap.Flag = Flag; etc.
void iconMap;
iconMap.Globe = Globe;
iconMap.Landmark = Landmark;
iconMap.Briefcase = Briefcase;
iconMap.Cpu = Cpu;
iconMap.BrainCircuit = BrainCircuit;
iconMap.Dumbbell = Dumbbell;
iconMap.CircleDot = CircleDot;
iconMap.FlaskConical = FlaskConical;
iconMap.HeartPulse = HeartPulse;
iconMap.Clapperboard = Clapperboard;
iconMap.Palette = Palette;
iconMap.CloudRain = CloudRain;

// ---------- Sub-components ----------

function StyleCard({
  active,
  onClick,
  icon,
  title,
  body,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg border-2 p-5 text-left transition-all ${
        active
          ? 'border-crimson bg-crimson/5 dark:bg-crimson/10'
          : 'border-ink/15 hover:border-crimson/50 dark:border-cream-ink/15 dark:hover:border-crimson/50'
      }`}
    >
      <div
        className={`inline-flex h-10 w-10 items-center justify-center rounded-full ${
          active ? 'bg-crimson text-paper' : 'border border-ink/20 text-ink/60 dark:border-cream-ink/20 dark:text-cream-ink/95'
        }`}
      >
        {icon}
      </div>
      <h3 className="mt-3 font-display text-lg font-bold text-ink dark:text-cream-ink">{title}</h3>
      <p className="mt-1 font-body text-sm text-ink/65 dark:text-cream-ink/95">{body}</p>
      {active && (
        <p className="mt-2 inline-flex items-center gap-1 font-ui text-xs font-semibold uppercase tracking-wider text-crimson">
          <Check className="h-3.5 w-3.5" />
          Selected
        </p>
      )}
    </button>
  );
}

function LanguageCard({
  active,
  onClick,
  label,
  sub,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  sub: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg border-2 p-5 text-left transition-all ${
        active
          ? 'border-crimson bg-crimson/5 dark:bg-crimson/10'
          : 'border-ink/15 hover:border-crimson/50 dark:border-cream-ink/15 dark:hover:border-crimson/50'
      }`}
    >
      <h3 className="font-display text-2xl font-bold text-ink dark:text-cream-ink">{label}</h3>
      <p className="mt-1 font-body text-sm text-ink/65 dark:text-cream-ink/95">{sub}</p>
      {active && (
        <p className="mt-2 inline-flex items-center gap-1 font-ui text-xs font-semibold uppercase tracking-wider text-crimson">
          <Check className="h-3.5 w-3.5" />
          Selected
        </p>
      )}
    </button>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
      role="switch"
      aria-checked={on}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${
        on ? 'bg-crimson' : 'bg-ink/20 dark:bg-cream-ink/20'
      }`}
    >
      <span
        className={`absolute top-1 h-5 w-5 rounded-full bg-paper shadow-sm transition-transform dark:bg-cream-ink ${
          on ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

function PrintingAnimation() {
  return (
    <div className="inline-flex items-center gap-3 rounded-full bg-crimson/10 px-6 py-3">
      <div className="flex items-end gap-1">
        <span className="h-2 w-1 animate-pulse rounded-full bg-crimson [animation-delay:0ms]" />
        <span className="h-3 w-1 animate-pulse rounded-full bg-crimson [animation-delay:150ms]" />
        <span className="h-4 w-1 animate-pulse rounded-full bg-crimson [animation-delay:300ms]" />
        <span className="h-3 w-1 animate-pulse rounded-full bg-crimson [animation-delay:450ms]" />
        <span className="h-2 w-1 animate-pulse rounded-full bg-crimson [animation-delay:600ms]" />
      </div>
      <span className="font-ui text-sm font-semibold uppercase tracking-wider text-crimson">
        Going to press…
      </span>
    </div>
  );
}

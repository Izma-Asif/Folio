import { useEffect, useState } from 'react';
import { CloudSun, Download, Languages, PenLine, Printer, RefreshCw, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Edition, Language } from '@/types';
import {
  generateEdition,
  getPdfUrl,
  getEditions,
  trackEvent,
  getUser,
  updatePreferences,
  sendEditorNote,
} from '@/api';
import Masthead from '@/components/Masthead';
import StoryCard from '@/components/StoryCard';
import { PaperSkeleton } from '@/components/Skeleton';

export default function Paper() {
  const [edition, setEdition] = useState<Edition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
    const [note, setNote] = useState('');
  const [noteMsg, setNoteMsg] = useState<string | null>(null);

  const handleNote = async () => {
    const text = note.trim();
    if (!text) return;
    setGenerating(true);
    setNoteMsg(null);
    try {
      const res = await sendEditorNote({ message: text } as any);
      setNoteMsg(res.summary || 'Got it. Your editor will adjust tomorrow\u2019s paper.');
      setNote('');
      const currentLang = edition?.language === 'ur' ? 'ur' : undefined;
      const ed = await generateEdition(currentLang as any);
      setEdition(ed);
    } catch {
      setNoteMsg('Your editor could not take that note right now. Try again.');
    } finally {
      setGenerating(false);
    }
  };
  const user = getUser();
  const isUrdu = edition?.language === 'ur';
  const showImages = user?.visual_mode !== 'reader';

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const eds = await getEditions(1);
        if (active) {
          setEdition(eds[0] ?? null);
          setLoading(false);
        }
      } catch {
        if (active) {
          setError("We couldn't set the type this morning. Please try again.");
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const handleRegenerate = async () => {
    setGenerating(true);
    try {
      const currentLang = edition?.language === 'ur' ? 'ur' : undefined;
      const ed = await generateEdition(currentLang as any);
      setEdition(ed);
    } catch {
      setError('Could not regenerate. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleLanguage = async (lang: Language) => {
    setGenerating(true);
    try {
      await updatePreferences({ language: lang });
      const ed = await generateEdition(lang);
      setEdition(ed);
    } catch {
      setError('Could not switch language. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handlePdf = async () => {
    if (!edition) return;
    const url = await getPdfUrl(edition.id);
    await trackEvent({ type: 'pdf', editionId: edition.id });
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return <PaperSkeleton />;
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4 text-center">
        <div>
          <AlertCircle className="mx-auto h-10 w-10 text-crimson" />
          <p className="mt-4 font-display text-2xl font-bold text-ink dark:text-cream-ink">
            The presses stalled
          </p>
          <p className="mt-2 max-w-sm font-body text-ink/70 dark:text-cream-ink/95">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!edition) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4 text-center">
        <div>
          <Printer className="mx-auto h-10 w-10 text-crimson" />
          <p className="mt-4 font-display text-2xl font-bold text-ink dark:text-cream-ink">
            No edition yet
          </p>
          <p className="mt-2 max-w-sm font-body text-ink/70 dark:text-cream-ink/95">
            Build your paper to start receiving daily editions.
          </p>
          <Link
            to="/onboarding"
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
          >
            Build my paper →
          </Link>
        </div>
      </div>
    );
  }

  const lead = edition.stories.find((s) => s.kind === 'lead') ?? edition.stories[0];
  const standards = edition.stories.filter((s) => s.kind === 'standard');
  const opinion = edition.stories.find((s) => s.kind === 'opinion');
  const briefs = edition.stories.filter((s) => s.kind === 'brief');

  const btn =
    'inline-flex items-center gap-1.5 rounded-full border border-ink/20 px-3 py-1.5 font-ui text-xs uppercase tracking-wider text-ink transition-colors hover:bg-ink hover:text-paper disabled:opacity-50 dark:border-crimson/50 dark:text-crimson dark:hover:bg-crimson dark:hover:text-paper';

  return (
    <div className="paper-texture pb-20">
      <div className="mx-auto max-w-broadsheet px-4 py-10 sm:px-6">
        <Masthead edition={edition} />

        {/* Toolbar */}
        <div className="no-print mt-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-ui text-sm text-ink/70 dark:text-cream-ink/95">
            <CloudSun className="h-4 w-4 text-crimson" />
            <span>
              {edition.weather.temp}°F · {edition.weather.condition} · H {edition.weather.high}° / L{' '}
              {edition.weather.low}°
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleLanguage(isUrdu ? 'en' : 'ur')}
              disabled={generating}
              className={btn}
            >
              <Languages className="h-3.5 w-3.5" />
              {isUrdu ? 'ENGLISH' : 'اردو'}
            </button>
            <button onClick={handleRegenerate} disabled={generating} className={btn}>
              <RefreshCw className={`h-3.5 w-3.5 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Reprinting' : 'Regenerate'}
            </button>
            <button onClick={handlePrint} className={btn}>
              <Printer className="h-3.5 w-3.5" />
              Print
            </button>
            <button onClick={handlePdf} className={btn}>
              <Download className="h-3.5 w-3.5" />
              PDF
            </button>
          </div>
        </div>

        {/* Ticker */}
        <div className="no-print mt-4 overflow-hidden border-y border-ink/15 dark:border-cream-ink/15">
          <div className="flex whitespace-nowrap py-2">
            <div className="flex animate-ticker">
              {[...edition.ticker, ...edition.ticker].map((t, i) => (
                <span
                  key={i}
                  className="mx-6 font-ui text-xs uppercase tracking-wider text-ink/60 dark:text-cream-ink/95"
                >
                  ● {t}
                </span>
              ))}
            </div>
          </div>
        </div>
        {/* Translation error banner */}
        {edition.translationError && (
          <div className="no-print mt-4 flex items-center gap-2 rounded-lg border border-amber-400/50 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-900/20 dark:text-amber-200">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {edition.translationError}
          </div>
        )}
        {/* Tell your editor */}
        <div className="no-print mt-4 rounded-lg border border-ink/15 p-4 dark:border-cream-ink/15">
          <label className="block">
            <span className="inline-flex items-center gap-2 font-ui text-xs font-semibold uppercase tracking-wider text-ink/60 dark:text-cream-ink/95">
              <PenLine className="h-3.5 w-3.5" />
              Tell your editor
            </span>
            <div className="mt-2 flex gap-2">
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleNote()}
                disabled={generating}
                placeholder="e.g. less politics, more startups, keep it short"
                className="w-full rounded-md border border-ink/20 bg-paper/50 px-4 py-2.5 font-body text-sm text-ink outline-none focus:border-crimson dark:border-crimson/40 dark:bg-navy-2/40 dark:text-cream-ink"
              />
              <button
                onClick={handleNote}
                disabled={generating || !note.trim()}
                className="shrink-0 rounded-full bg-crimson px-5 py-2.5 font-ui text-xs font-semibold uppercase tracking-wider text-paper transition-all disabled:opacity-40 enabled:hover:bg-crimson-hover"
              >
                {generating ? 'Updating\u2026' : 'Send'}
              </button>
            </div>
          </label>
          {noteMsg && (
            <p className="mt-2 font-body text-sm italic text-ink/70 dark:text-cream-ink/95">
              {noteMsg}
            </p>
          )}
        </div>
        {/* Everything below follows the reader's language direction */}
        <div dir={isUrdu ? 'rtl' : 'ltr'} lang={isUrdu ? 'ur' : 'en'}>
          {/* Editor's note */}
          <p className="mt-6 max-w-2xl font-body text-sm italic leading-relaxed text-ink/70 dark:text-cream-ink/95">
            <span className="font-ui not-italic text-[11px] uppercase tracking-[0.2em] text-crimson">
              From the editor ·{' '}
            </span>
            {edition.editorNote}
          </p>

          {/* Lead */}
          <div className="mt-8">
            <StoryCard story={lead} variant="lead" showImages={showImages} />
          </div>

          <div className="my-10 rule-double border-ink/80 dark:border-cream-ink/80" />

          {/* Standard stories grid */}
          <div className="grid gap-10 md:grid-cols-2 md:gap-x-12 md:gap-y-10">
            {standards.map((s) => (
              <StoryCard key={s.id} story={s} variant="standard" showImages={showImages} />
            ))}
          </div>

          {/* Briefs + Opinion */}
          <div className="my-10 rule-thin border-ink/20 dark:border-cream-ink/20" />

          <div className="grid gap-10 md:grid-cols-3">
            <div className="md:col-span-1">
              <h3 className="font-display text-xl font-black uppercase tracking-tight text-ink dark:text-cream-ink">
                {isUrdu ? 'مختصر خبریں' : 'In Brief'}
              </h3>
              <div className="mt-3 divide-y divide-ink/15 dark:divide-cream-ink/15">
                {briefs.map((b) => (
                  <StoryCard key={b.id} story={b} variant="brief" showImages={false} />
                ))}
              </div>
            </div>
            <div className="md:col-span-2">
              {opinion && <StoryCard story={opinion} variant="opinion" showImages={false} />}
            </div>
          </div>
        </div>

        {user && (
          <p className="mt-12 text-center font-ui text-xs uppercase tracking-[0.2em] text-ink/40 dark:text-cream-ink/95">
            Prepared for {user.name} · Day {user.streak} of your streak
          </p>
        )}
      </div>
    </div>
  );
}
import { useEffect, useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Flame,
  Mail,
  Send,
  Bookmark,
  SkipForward,
  PenLine,
  Eye,
  BookOpen,
  Sparkles,
  Save,
} from 'lucide-react';
import { AlertCircle } from 'lucide-react';
import type { InterestWeight, UserProfile, VisualMode } from '@/types';
import {
  getWeights,
  getUser,
  fetchUserProfile,
  listAllInterests,
  sendEditorNote,
  trackEvent,
  getRecentActivity,
  getEditorNotes,
  getLearningSummary,
  updatePreferences,
  type ActivityEntry,
  type EditorNoteEntry,
  type LearningSummary,
} from '@/api';
import { Link } from 'react-router-dom';
import { ProfileSkeleton } from '@/components/Skeleton';

export default function Profile() {
  const [user, setUserState] = useState<UserProfile | null>(getUser());
  const [weights, setWeights] = useState<InterestWeight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [noteSent, setNoteSent] = useState(false);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [editorNotes, setEditorNotes] = useState<EditorNoteEntry[]>([]);
  const [learning, setLearning] = useState<LearningSummary | null>(null);
  const [calmMode, setCalmMode] = useState(user?.calm_mode ?? false);
  const [visualMode, setVisualMode] = useState<VisualMode>(user?.visual_mode ?? 'visual');
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [prefsSaved, setPrefsSaved] = useState(false);
  const allInterests = listAllInterests();

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        let currentUser = user || getUser();
        if (!currentUser) {
          currentUser = await fetchUserProfile();
          if (currentUser && active) {
            setUserState(currentUser);
            setCalmMode(currentUser.calm_mode);
            setVisualMode(currentUser.visual_mode);
          }
        }

        const [w, act, notes, learn] = await Promise.all([
          getWeights(),
          getRecentActivity(8),
          getEditorNotes(),
          getLearningSummary(),
        ]);
        if (active) {
          setWeights(w);
          setActivity(act);
          setEditorNotes(notes);
          setLearning(learn);
          setLoading(false);
        }
      } catch {
        if (active) {
          setError("We couldn't load your profile data. Please try again.");
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const sortedWeights = [...weights].sort((a, b) => b.weight - a.weight);

  const handleWeightChange = (interest: string, newWeight: number) => {
    setWeights((prev) =>
      prev.map((w) => (w.interest === interest ? { ...w, weight: newWeight } : w)),
    );
  };

  const handleSendNote = async () => {
    if (!note.trim()) return;
    await sendEditorNote({ editionId: 'today', message: note.trim() });
    await trackEvent({ type: 'share' });
    setEditorNotes((prev) => [
      { id: `note_${Date.now()}`, message: note.trim(), date: new Date().toISOString().slice(0, 10) },
      ...prev,
    ]);
    setNote('');
    setNoteSent(true);
    setTimeout(() => setNoteSent(false), 3000);
  };

  const handleSavePrefs = async () => {
    setSavingPrefs(true);
    await updatePreferences({ calm_mode: calmMode, visual_mode: visualMode });
    const updated = getUser();
    setUserState(updated);
    setSavingPrefs(false);
    setPrefsSaved(true);
    setTimeout(() => setPrefsSaved(false), 3000);
  };

  if (loading) {
    return <ProfileSkeleton />;
  }

  if (error) {
    return (
      <div className="paper-texture min-h-[calc(100vh-4rem)]">
        <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
          <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
            <AlertCircle className="h-10 w-10 text-crimson" />
            <p className="mt-4 font-display text-2xl font-bold text-ink dark:text-cream-ink">
              Profile unavailable
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

  if (!user) {
    return (
      <div className="paper-texture min-h-[calc(100vh-4rem)]">
        <div className="mx-auto max-w-lg px-4 py-20 text-center sm:px-6">
          <h1 className="font-display text-3xl font-black text-ink dark:text-cream-ink">
            No profile yet
          </h1>
          <p className="mx-auto mt-3 max-w-sm font-body text-base text-ink/70 dark:text-cream-ink/95">
            Complete onboarding to personalize your edition and see your interest weights here.
          </p>
          <Link
            to="/onboarding"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-crimson px-6 py-3 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all hover:bg-crimson-hover hover:-translate-y-0.5"
          >
            Start onboarding →
          </Link>
        </div>
      </div>
    );
  }

  const interestLabels = user.interests.map(
    (id) => allInterests.find((i) => i.id === id)?.label ?? id,
  );

  return (
    <div className="paper-texture min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        {/* Header */}
        <div className="text-center">
          <p className="font-ui text-xs uppercase tracking-[0.25em] text-crimson">
            Subscriber card
          </p>
          <h1 className="mt-2 font-display text-4xl font-black text-ink dark:text-cream-ink">
            {user.name}
          </h1>
          {user.email && (
            <p className="mt-1 inline-flex items-center gap-1.5 font-ui text-sm text-ink/60 dark:text-cream-ink/95">
              <Mail className="h-3.5 w-3.5" />
              {user.email}
            </p>
          )}
        </div>

        <div className="mx-auto mt-5 max-w-xs rule-double border-ink/70 dark:border-cream-ink/70" />

        {/* Stats */}
        <div className="mt-8 grid grid-cols-3 gap-px border border-ink/15 bg-ink/15 dark:border-cream-ink/15 dark:bg-cream-ink/15">
          <Stat label="Day streak" value={String(user.streak)} icon={<Flame className="h-4 w-4" />} />
          <Stat label="Interests" value={String(user.interests.length)} />
          <Stat
            label="Member since"
            value={new Date(user.createdAt).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
          />
        </div>

        {/* Learning summary */}
        {learning && (
          <div className="mt-8 flex items-center gap-3 rounded-lg border border-crimson/25 bg-crimson/5 p-4 dark:border-crimson/30 dark:bg-crimson/10">
            <Sparkles className="h-5 w-5 shrink-0 text-crimson" />
            <p className="font-body text-sm text-ink/80 dark:text-cream-ink/95">
              <span className="font-ui text-xs font-semibold uppercase tracking-wider text-crimson">
                Your paper learned:{' '}
              </span>
              more{' '}
              {learning.more.map((t, i) => (
                <span key={t}>
                  {i > 0 && ', '}
                  <span className="font-semibold text-ink dark:text-cream-ink">{t}</span>
                </span>
              ))}
              , less{' '}
              {learning.less.map((t, i) => (
                <span key={t}>
                  {i > 0 && ', '}
                  <span className="font-semibold text-ink dark:text-cream-ink">{t}</span>
                </span>
              ))}
              .
            </p>
          </div>
        )}

        {/* Interest weights with sliders */}
        <section className="mt-12">
          <h2 className="font-display text-2xl font-bold text-ink dark:text-cream-ink">
            My Interests
          </h2>
          <p className="mt-1 font-body text-sm text-ink/60 dark:text-cream-ink/95">
            Drag a slider to tune how much each topic influences your front page.
          </p>

          {loading ? (
            <p className="mt-4 font-ui text-sm uppercase tracking-wider text-ink/50 dark:text-cream-ink/95">
              Calculating…
            </p>
          ) : (
            <div className="mt-6 space-y-5">
              {sortedWeights.map((w) => (
                <WeightRow key={w.interest} weight={w} onChange={handleWeightChange} />
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {interestLabels.map((label) => (
              <span
                key={label}
                className="rounded-full border border-ink/20 px-3 py-1 font-ui text-xs text-ink dark:border-cream-ink/20 dark:text-cream-ink"
              >
                {label}
              </span>
            ))}
          </div>
        </section>

        <div className="my-10 rule-thin border-ink/15 dark:border-cream-ink/15" />

        {/* Preferences toggles */}
        <section>
          <h2 className="font-display text-2xl font-bold text-ink dark:text-cream-ink">
            Preferences
          </h2>

          {/* Visual / Reader mode */}
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <PrefCard
              active={visualMode === 'visual'}
              onClick={() => setVisualMode('visual')}
              icon={<Eye className="h-5 w-5" />}
              title="Visual"
              body="Photos, illustrations, rich layout."
            />
            <PrefCard
              active={visualMode === 'reader'}
              onClick={() => setVisualMode('reader')}
              icon={<BookOpen className="h-5 w-5" />}
              title="Reader"
              body="Text-first, distraction-free columns."
            />
          </div>

          {/* Calm mode toggle */}
          <div className="mt-4 flex items-center justify-between rounded-lg border border-ink/15 p-4 dark:border-cream-ink/15">
            <div>
              <p className="font-ui text-sm font-semibold text-ink dark:text-cream-ink">
                Calm mode
              </p>
              <p className="mt-0.5 font-body text-sm text-ink/60 dark:text-cream-ink/95">
                Fewer distressing stories on the front page.
              </p>
            </div>
            <Toggle on={calmMode} onChange={setCalmMode} />
          </div>

          <button
            onClick={handleSavePrefs}
            disabled={savingPrefs}
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all disabled:opacity-50 enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
          >
            <Save className="h-4 w-4" />
            {savingPrefs ? 'Saving…' : 'Save preferences'}
          </button>
          {prefsSaved && (
            <span className="ml-3 font-ui text-sm text-crimson animate-fade-up">
              Saved.
            </span>
          )}
        </section>

        <div className="my-10 rule-thin border-ink/15 dark:border-cream-ink/15" />

        {/* Recent activity */}
        <section>
          <h2 className="font-display text-2xl font-bold text-ink dark:text-cream-ink">
            Recent activity
          </h2>
          <p className="mt-1 font-body text-sm text-ink/60 dark:text-cream-ink/95">
            What you've saved and skipped over the last few editions.
          </p>

          {loading ? (
            <p className="mt-4 font-ui text-sm uppercase tracking-wider text-ink/50 dark:text-cream-ink/95">
              Loading…
            </p>
          ) : (
            <ul className="mt-5 divide-y divide-ink/10 dark:divide-cream-ink/10">
              {activity.map((entry) => (
                <li key={entry.id} className="flex items-start gap-3 py-3">
                  {entry.type === 'saved' ? (
                    <Bookmark className="mt-0.5 h-4 w-4 shrink-0 text-crimson" />
                  ) : (
                    <SkipForward className="mt-0.5 h-4 w-4 shrink-0 text-ink/40 dark:text-cream-ink/95" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-body text-sm text-ink/85 dark:text-cream-ink/95">
                      <span className="font-ui text-xs font-semibold uppercase tracking-wider text-ink/50 dark:text-cream-ink/95">
                        You {entry.type === 'saved' ? 'saved' : 'skipped'}:{' '}
                      </span>
                      {entry.headline}
                      {entry.type === 'skipped' && (
                        <span className="text-ink/45 dark:text-cream-ink/95"> (Not interested)</span>
                      )}
                    </p>
                    <p className="mt-0.5 font-ui text-[11px] uppercase tracking-wider text-ink/40 dark:text-cream-ink/95">
                      {entry.section} · {entry.editionDate}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="my-10 rule-thin border-ink/15 dark:border-cream-ink/15" />

        {/* Notes to editor */}
        <section>
          <h2 className="font-display text-2xl font-bold text-ink dark:text-cream-ink">
            Notes to your editor
          </h2>
          <p className="mt-1 font-body text-sm text-ink/60 dark:text-cream-ink/95">
            Send a note about today's edition. We read every one.
          </p>

          <div className="mt-4">
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Dear editor…"
              className="w-full resize-none rounded-md border border-ink/20 bg-paper/50 p-4 font-body text-sm text-ink outline-none transition-colors focus:border-crimson dark:border-crimson/40 dark:bg-navy-2/40 dark:text-cream-ink"
            />
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={handleSendNote}
                disabled={!note.trim()}
                className="inline-flex items-center gap-2 rounded-full bg-crimson px-5 py-2.5 font-ui text-sm font-semibold uppercase tracking-wider text-paper transition-all disabled:opacity-40 enabled:hover:bg-crimson-hover enabled:hover:-translate-y-0.5"
              >
                <Send className="h-4 w-4" />
                Send note
              </button>
              {noteSent && (
                <span className="font-ui text-sm text-crimson animate-fade-up">
                  Thank you — your note is on the editor's desk.
                </span>
              )}
            </div>
          </div>

          {/* Note history */}
          {editorNotes.length > 0 && (
            <ul className="mt-6 divide-y divide-ink/10 dark:divide-cream-ink/10">
              {editorNotes.map((entry) => (
                <li key={entry.id} className="flex items-start gap-3 py-3">
                  <PenLine className="mt-0.5 h-4 w-4 shrink-0 text-ink/40 dark:text-cream-ink/95" />
                  <div className="min-w-0 flex-1">
                    <p className="font-body text-sm italic text-ink/80 dark:text-cream-ink/95">
                      "{entry.message}"
                    </p>
                    <p className="mt-0.5 font-ui text-[11px] uppercase tracking-wider text-ink/40 dark:text-cream-ink/95">
                      {entry.date}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

// ---------- Sub-components ----------

function WeightRow({
  weight,
  onChange,
}: {
  weight: InterestWeight;
  onChange: (interest: string, newWeight: number) => void;
}) {
  const pct = Math.round(weight.weight * 100);
  return (
    <div className="animate-fade-up">
      <div className="flex items-center justify-between">
        <span className="font-ui text-sm font-medium text-ink dark:text-cream-ink">
          {weight.interest}
        </span>
        <span className="inline-flex items-center gap-1.5 font-ui text-xs text-ink/55 dark:text-cream-ink">
          {weight.trend === 'up' && <TrendingUp className="h-3.5 w-3.5 text-crimson" />}
          {weight.trend === 'down' && <TrendingDown className="h-3.5 w-3.5 text-ink/45 dark:text-cream-ink/95" />}
          {weight.trend === 'flat' && <Minus className="h-3.5 w-3.5 text-ink/35 dark:text-cream-ink" />}
          {weight.weight.toFixed(2)}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-ink/10 dark:bg-cream-ink/10">
          <div
            className="h-full rounded-full bg-crimson transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={pct}
          onChange={(e) => onChange(weight.interest, Number(e.target.value) / 100)}
          className="h-1.5 w-32 cursor-pointer appearance-none rounded-full bg-ink/15 accent-crimson dark:bg-cream-ink/15"
          aria-label={`Adjust ${weight.interest} weight`}
        />
      </div>
    </div>
  );
}

function PrefCard({
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
      className={`flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all ${
        active
          ? 'border-crimson bg-crimson/5 dark:bg-crimson/10'
          : 'border-ink/15 hover:border-crimson/50 dark:border-cream-ink/15 dark:hover:border-crimson/50'
      }`}
    >
      <div
        className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
          active ? 'bg-crimson text-paper' : 'border border-ink/20 text-ink/55 dark:border-cream-ink/20 dark:text-cream-ink'
        }`}
      >
        {icon}
      </div>
      <div>
        <p className="font-ui text-sm font-semibold text-ink dark:text-cream-ink">{title}</p>
        <p className="font-body text-xs text-ink/60 dark:text-cream-ink/95">{body}</p>
      </div>
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

function Stat({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="bg-paper p-4 text-center dark:bg-navy">
      <p className="font-ui text-[11px] uppercase tracking-wider text-ink/50 dark:text-cream-ink/95">
        {label}
      </p>
      <p className="mt-1 inline-flex items-center gap-1.5 font-display text-xl font-bold text-ink dark:text-cream-ink">
        {icon}
        {value}
      </p>
    </div>
  );
}

import type {
  AnalyticsEvent,
  Edition,
  EditorNotePayload,
  Interest,
  InterestWeight,
  Language,
  Story,
  UserProfile,
  VisualMode,
} from '@/types';

export const STORAGE_KEY = 'folio_user_id';
export const PROFILE_KEY = 'folio_user_profile';

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

// Static interest taxonomy used for selection UI and categorization
export const ALL_INTERESTS: Interest[] = [
  { id: 'pakistan', label: 'Pakistan', category: 'World', icon: 'Flag' },
  { id: 'world', label: 'World', category: 'World', icon: 'Globe' },
  { id: 'politics', label: 'Politics', category: 'World', icon: 'Landmark' },
  { id: 'business', label: 'Business', category: 'Money', icon: 'Briefcase' },
  { id: 'tech', label: 'Tech', category: 'World', icon: 'Cpu' },
  { id: 'ai', label: 'AI', category: 'World', icon: 'BrainCircuit' },
  { id: 'sports', label: 'Sports', category: 'Life', icon: 'Dumbbell' },
  { id: 'cricket', label: 'Cricket', category: 'Life', icon: 'CircleDot' },
  { id: 'science', label: 'Science', category: 'World', icon: 'FlaskConical' },
  { id: 'health', label: 'Health', category: 'Life', icon: 'HeartPulse' },
  { id: 'entertainment', label: 'Entertainment', category: 'Life', icon: 'Clapperboard' },
  { id: 'culture', label: 'Culture', category: 'Life', icon: 'Palette' },
  { id: 'climate', label: 'Climate', category: 'World', icon: 'CloudRain' },
];

export function listAllInterests(): Interest[] {
  return ALL_INTERESTS;
}

// ---------- User ID & Persistence ----------

export function getUserId(): string {
  if (typeof window === 'undefined') return 'default_user';
  return window.localStorage.getItem(STORAGE_KEY) || 'default_user';
}

export function setUserId(id: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, id);
  }
}

let cachedUser: UserProfile | null = null;

export function getUser(): UserProfile | null {
  if (cachedUser) return cachedUser;
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage.getItem(PROFILE_KEY);
      if (stored) {
        cachedUser = JSON.parse(stored);
        return cachedUser;
      }
    } catch {
      // ignore JSON parse error
    }
  }
  return null;
}

export function setUser(user: UserProfile | null): void {
  cachedUser = user;
  if (typeof window !== 'undefined') {
    if (user) {
      window.localStorage.setItem(PROFILE_KEY, JSON.stringify(user));
      window.localStorage.setItem(STORAGE_KEY, user.id);
    } else {
      window.localStorage.removeItem(PROFILE_KEY);
    }
  }
}

// ---------- HTTP Client with error formatting ----------

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errorMsg = `API request failed: ${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') {
        errorMsg = data.detail;
      } else if (data.detail && typeof data.detail === 'object') {
        errorMsg = JSON.stringify(data.detail);
      } else if (data.message) {
        errorMsg = data.message;
      }
    } catch {
      // Response was not JSON
    }
    throw new Error(errorMsg);
  }

  return res.json() as Promise<T>;
}

function titleCase(s: string): string {
  if (!s) return '';
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------- Types for User & Profile ----------

export interface CreateUserInput {
  name?: string;
  email?: string;
  interests: string[];
  custom_feeds?: string[];
  language?: Language;
  calm_mode?: boolean;
  visual_mode?: VisualMode;
}

export async function createUser(input: CreateUserInput): Promise<UserProfile> {
  const payload = {
    interests: input.interests,
    custom_feeds: input.custom_feeds || [],
    language: input.language || 'en',
    calm_mode: input.calm_mode ?? false,
    visual_mode: input.visual_mode || 'visual',
  };

  const res = await apiFetch<{ user_id: string }>('/api/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

  const id = res.user_id;
  setUserId(id);

  const profile: UserProfile = {
    id,
    name: input.name || 'Reader',
    email: input.email || '',
    interests: input.interests,
    custom_feeds: input.custom_feeds || [],
    language: input.language || 'en',
    calm_mode: input.calm_mode ?? false,
    visual_mode: input.visual_mode || 'visual',
    createdAt: new Date().toISOString(),
    streak: 1,
    lastRead: null,
  };

  setUser(profile);
  return profile;
}

export async function fetchUserProfile(userId?: string): Promise<UserProfile | null> {
  const uid = userId || getUserId();
  try {
    const raw = await apiFetch<any>(`/api/users/${uid}`);
    if (!raw) return null;
    const profile: UserProfile = {
      id: raw.id,
      name: raw.name || 'Reader',
      email: raw.email || '',
      interests: raw.interests || [],
      custom_feeds: raw.custom_feeds || [],
      language: raw.language || 'en',
      calm_mode: !!raw.calm_mode,
      visual_mode: raw.visual_mode || 'visual',
      createdAt: raw.created_at || new Date().toISOString(),
      streak: 1,
      lastRead: null,
    };
    setUser(profile);
    return profile;
  } catch {
    return getUser();
  }
}

// ---------- Interest Inference ----------

export async function inferInterests(
  input: { topics: string[]; sources?: string[] },
): Promise<string[]> {
  const textQuery = [
    input.topics.join(', '),
    ...(input.sources || []),
  ].filter(Boolean).join(' ');

  const res = await apiFetch<{
    topics: string[];
    style: string;
    summary: string;
  }>('/api/infer-interests', {
    method: 'POST',
    body: JSON.stringify({ text: textQuery || 'world technology news' }),
  });

  if (Array.isArray(res.topics) && res.topics.length > 0) {
    return res.topics.map((t) => t.toLowerCase());
  }
  return input.topics;
}

// ---------- Edition Adapter & Mapping ----------

function articleToStory(
  a: any,
  kind: 'lead' | 'standard' | 'brief' | 'opinion',
  defaultSection: string = 'General'
): Story {
  const section = a.topic ? titleCase(a.topic) : defaultSection;
  const headline = a.title || 'Untitled Dispatch';
  const dek = a.summary || '';
  const byline = a.source ? `By ${a.source}` : 'By the Folio Desk';

  const bodyParagraphs: string[] = [];
  if (a.summary) {
    bodyParagraphs.push(a.summary);
  }
  if (a.why) {
    bodyParagraphs.push(a.why);
  }
  if (Array.isArray(a.angles) && a.angles.length > 0) {
    const angleText = a.angles
      .map((ang: any) => `${ang.source}: ${ang.focus}`)
      .join(' • ');
    bodyParagraphs.push(`Angles: ${angleText}`);
  }
  if (bodyParagraphs.length === 0) {
    bodyParagraphs.push(headline);
  }

  return {
    id: String(a.id || `story_${Math.random().toString(36).slice(2, 9)}`),
    kind,
    section,
    headline,
    dek,
    byline,
    body: bodyParagraphs,
    readingTime: Math.max(1, Math.round((dek.length + 120) / 200)),
    tags: [a.topic?.toLowerCase(), a.tone].filter(Boolean),
    imageUrl: a.image_url || undefined,
  };
}

function mapEdition(raw: any): Edition {
  const stories: Story[] = [];

  // 1. Lead story
  if (raw.lead && raw.lead.title) {
    stories.push(articleToStory(raw.lead, 'lead', 'Front Page'));
  }

  // 2. Sections
  const sectionArticles: any[] = [];
  if (Array.isArray(raw.sections)) {
    for (const sec of raw.sections) {
      if (Array.isArray(sec.articles)) {
        for (const art of sec.articles) {
          sectionArticles.push({ ...art, topic: art.topic || sec.topic });
        }
      }
    }
  }

  // Standards (first 4 section stories)
  const standards = sectionArticles.slice(0, 4).map((a) => articleToStory(a, 'standard'));
  stories.push(...standards);

  // Opinion (5th section story, or analytical piece)
  const opinionCandidate = sectionArticles[4];
  if (opinionCandidate) {
    stories.push(articleToStory(opinionCandidate, 'opinion', 'Opinion'));
  }

  // Briefs (remaining section stories + explore)
  const briefArticles = [
    ...sectionArticles.slice(5),
    ...(Array.isArray(raw.explore) ? raw.explore : []),
  ];
  const briefs = briefArticles.map((a) => articleToStory(a, 'brief', 'In Brief'));
  stories.push(...briefs);

  // Fallback story if completely empty
  if (stories.length === 0) {
    stories.push({
      id: 'story_welcome',
      kind: 'lead',
      section: 'Front Page',
      headline: 'Welcome to Your Daily Folio',
      dek: 'Your bespoke morning broadsheet will be prepared with today’s edition.',
      byline: 'By the Folio Desk',
      body: ['The morning presses run daily to bring you deep, balanced coverage across your chosen interests.'],
      readingTime: 2,
      tags: ['welcome'],
    });
  }

  // Weather block
  const weather = {
    temp: 68,
    condition: 'Clear skies',
    high: 74,
    low: 58,
  };

  // Ticker lines from three_things or defaults
  const ticker = Array.isArray(raw.three_things) && raw.three_things.length > 0
    ? raw.three_things
    : [
        'FOLIO • Published every morning, for you',
        'Curated intelligence across all your chosen sources',
        'Balanced coverage with multi-perspective editorial angles',
      ];

  // Editor's note
  let editorNote = 'Good morning. Your daily edition is ready.';
  if (raw.editor_note && typeof raw.editor_note === 'object') {
    editorNote = raw.editor_note.note || raw.editor_note.summary || editorNote;
  } else if (Array.isArray(raw.changes) && raw.changes.length > 0) {
    editorNote = raw.changes.join('. ');
  } else if (raw.lead?.why) {
    editorNote = `Today's lead was chosen: ${raw.lead.why}`;
  }

  return {
    id: String(raw.id || `edition_${raw.date || raw.edition_date || new Date().toISOString().slice(0, 10)}`),
    date: raw.date || raw.edition_date || new Date().toISOString().slice(0, 10),
    headline: raw.masthead || 'The Morning Folio',
    weather,
    ticker,
    stories,
    editorNote,
  };
}

// ---------- Editions API ----------

export async function getEditions(limit = 14): Promise<Edition[]> {
  const userId = getUserId();
  let summaries: any[] = [];
  try {
    summaries = await apiFetch<any[]>(`/api/editions?user_id=${encodeURIComponent(userId)}&limit=${limit}`);
  } catch {
    summaries = [];
  }

  // If this user has no editions yet, try loading default sample edition
  if (!Array.isArray(summaries) || summaries.length === 0) {
    if (userId !== 'default_user') {
      try {
        summaries = await apiFetch<any[]>(`/api/editions?limit=${limit}`);
      } catch {
        summaries = [];
      }
    }
  }

  if (!Array.isArray(summaries) || summaries.length === 0) {
    return [];
  }

  // Fetch full details for each edition in parallel
  const editions = await Promise.all(
    summaries.map(async (s) => {
      try {
        const full = await getEdition(s.id);
        if (full) return full;
      } catch {
        // fallback to mapping from summary
      }
      return mapEdition({
        id: s.id,
        date: s.date,
        masthead: s.masthead,
        lead: s.lead_title ? { title: s.lead_title, topic: 'Front Page' } : undefined,
      });
    })
  );

  return editions.filter(Boolean) as Edition[];
}

export async function getEdition(id: string): Promise<Edition | null> {
  try {
    const raw = await apiFetch<any>(`/api/editions/${encodeURIComponent(id)}`);
    if (!raw) return null;
    return mapEdition(raw);
  } catch (err) {
    console.error('getEdition failed:', err);
    return null;
  }
}

export async function generateEdition(): Promise<Edition> {
  const userId = getUserId();
  const raw = await apiFetch<any>(`/api/editions/generate?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
  });

  const edition = mapEdition(raw);

  const user = getUser();
  if (user) {
    user.streak += 1;
    user.lastRead = new Date().toISOString();
    setUser(user);
  }

  return edition;
}

// ---------- Events & Telemetry ----------

export async function trackEvent(
  event: Omit<AnalyticsEvent, 'timestamp'> & { reason?: string; articleId?: string },
): Promise<void> {
  const userId = getUserId();
  let type: 'click' | 'save' | 'skip' = 'click';

  if (event.type === 'skip') {
    type = 'skip';
  } else if (event.type === 'share' || (event.type as any) === 'save') {
    type = 'save';
  } else {
    type = 'click';
  }

  const articleId = event.articleId || event.storyId;

  try {
    await apiFetch('/api/events', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        article_id: articleId && !articleId.startsWith('story_') ? articleId : null,
        type,
        reason: event.reason,
      }),
    });
  } catch (err) {
    console.warn('trackEvent failed:', err);
  }
}

// ---------- Weights & Learning ----------

export async function getWeights(): Promise<InterestWeight[]> {
  const userId = getUserId();
  try {
    const res = await apiFetch<{ weights: Record<string, number> }>(`/api/users/${userId}/weights`);
    const weightsObj = res.weights || {};
    return Object.entries(weightsObj).map(([topic, weight]) => ({
      interest: titleCase(topic),
      weight: Number(weight.toFixed(2)),
      trend: 'flat' as const,
    }));
  } catch (err) {
    console.error('getWeights failed:', err);
    return [];
  }
}

// ---------- Editor Notes ----------

export async function sendEditorNote(
  payload: EditorNotePayload,
): Promise<{ ok: true; summary?: string }> {
  const userId = getUserId();
  const text = payload.message;
  const res = await apiFetch<{ summary: string; applied: any }>(
    `/api/users/${userId}/editor-note`,
    {
      method: 'POST',
      body: JSON.stringify({ text }),
    },
  );
  return { ok: true, summary: res.summary };
}

export interface EditorNoteEntry {
  id: string;
  message: string;
  date: string;
}

export async function getEditorNotes(): Promise<EditorNoteEntry[]> {
  const userId = getUserId();
  try {
    const res = await apiFetch<any[]>(`/api/users/${userId}/editor-notes`);
    if (!Array.isArray(res)) return [];
    return res.map((n) => ({
      id: String(n.id),
      message: n.instruction || n.text || n.summary || 'Instruction note',
      date: n.created_at ? n.created_at.slice(0, 10) : new Date().toISOString().slice(0, 10),
    }));
  } catch (err) {
    console.error('getEditorNotes failed:', err);
    return [];
  }
}

// ---------- PDF Direct URL ----------

export async function getPdfUrl(editionId: string): Promise<string> {
  return `${BASE_URL}/api/editions/${encodeURIComponent(editionId)}/pdf`;
}

// ---------- Recent Activity ----------

export interface ActivityEntry {
  id: string;
  type: 'saved' | 'skipped';
  headline: string;
  section: string;
  editionDate: string;
  timestamp: string;
}

export async function getRecentActivity(limit = 8): Promise<ActivityEntry[]> {
  const userId = getUserId();
  try {
    const res = await apiFetch<{ activity?: any[] }>(`/api/users/${userId}/weights`);
    const list = res.activity || [];
    return list.slice(0, limit).map((a) => ({
      id: String(a.id || Math.random()),
      type: a.type === 'skip' ? 'skipped' : 'saved',
      headline: a.article_title || 'Article reading',
      section: 'News',
      editionDate: a.created_at ? a.created_at.slice(0, 10) : new Date().toISOString().slice(0, 10),
      timestamp: a.created_at || new Date().toISOString(),
    }));
  } catch (err) {
    console.error('getRecentActivity failed:', err);
    return [];
  }
}

// ---------- Learning Summary ----------

export interface LearningSummary {
  more: string[];
  less: string[];
}

export async function getLearningSummary(): Promise<LearningSummary> {
  const userId = getUserId();
  try {
    const res = await apiFetch<any>(`/api/users/${userId}/learning`);
    return {
      more: (res.top_topics || []).map((t: string) => titleCase(t)),
      less: (res.deprioritized_topics || []).map((t: string) => titleCase(t)),
    };
  } catch (err) {
    console.error('getLearningSummary failed:', err);
    return { more: [], less: [] };
  }
}

// ---------- Preferences Update ----------

export async function updatePreferences(input: {
  calm_mode?: boolean;
  visual_mode?: VisualMode;
  interests?: string[];
}): Promise<UserProfile | null> {
  const userId = getUserId();
  try {
    const res = await apiFetch<any>(`/api/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    });

    const current = getUser() || {
      id: userId,
      name: 'Reader',
      email: '',
      interests: [],
      custom_feeds: [],
      language: 'en' as const,
      calm_mode: false,
      visual_mode: 'visual' as const,
      createdAt: new Date().toISOString(),
      streak: 1,
      lastRead: null,
    };

    const updated: UserProfile = {
      ...current,
      calm_mode: res.calm_mode ?? input.calm_mode ?? current.calm_mode,
      visual_mode: res.visual_mode ?? input.visual_mode ?? current.visual_mode,
      interests: res.interests ?? input.interests ?? current.interests,
    };

    setUser(updated);
    return updated;
  } catch (err) {
    console.error('updatePreferences failed:', err);
    return getUser();
  }
}

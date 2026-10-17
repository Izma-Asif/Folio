export interface Interest {
  id: string;
  label: string;
  category: string;
  icon: string;
}

export type VisualMode = 'visual' | 'reader';
export type Language = 'en' | 'ur';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  interests: string[];
  custom_feeds: string[];
  language: Language;
  calm_mode: boolean;
  visual_mode: VisualMode;
  createdAt: string;
  streak: number;
  lastRead: string | null;
}

export type StoryKind = 'lead' | 'standard' | 'brief' | 'opinion';

export interface Story {
  id: string;
  kind: StoryKind;
  section: string;
  headline: string;
  dek: string;
  byline: string;
  body: string[];
  readingTime: number;
  tags: string[];
  imageUrl?: string;
  link?: string;
}

export interface Edition {
  id: string;
  date: string;
  headline: string;
  weather: { temp: number; condition: string; high: number; low: number };
  ticker: string[];
  stories: Story[];
  editorNote: string;
  language?: 'en' | 'ur';
  translationError?: string;
}

export interface InterestWeight {
  interest: string;
  weight: number;
  trend: 'up' | 'down' | 'flat';
}

export interface AnalyticsEvent {
  type: 'view' | 'click' | 'read' | 'share' | 'pdf';
  storyId?: string;
  editionId?: string;
  timestamp: string;
}

export interface EditorNotePayload {
  editionId: string;
  message: string;
}

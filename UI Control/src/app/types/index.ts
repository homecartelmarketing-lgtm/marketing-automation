import { TabType } from '../components/planning/FormatTabs';
import { FixtureData } from '../components/planning/FixtureCard';

export type { TabType, FixtureData };

export interface QueueJob {
  id: string;
  pipeline_type: string;
  pipeline_name: string;
  fixture_id: string;
  fixture_name: string;
  format_tab: string;
  subtab_index: number;
  table_id: string;
  enqueued_at?: number;
  started_at?: number;
  current_phase?: string;
  current_phase_index?: number;
  total_phases?: number;
  elapsed_seconds?: number;
  status?: string;
  max_items?: number;
  error?: string;
  logs?: string[];
}

export interface QueueHistoryItem {
  id: string;
  pipeline_name: string;
  fixture_name: string;
  format_tab: string;
  status: string;
  duration_seconds: number;
  finished_at: number;
  error?: string;
}

export interface PipelineExecutionState {
  status: 'idle' | 'running' | 'completed' | 'error' | 'stopped';
  active_fixture: string | null;
  active_table_id: string | null;
  current_phase: string;
  current_phase_index: number;
  total_phases: number;
  elapsed_seconds: number;
  logs: string[];
  error?: string | null;
}

export type StatusCounts = {
  P: number;
  S?: number;
  C: number;
  D: number;
  FM: number;
};

export type StatusCountMap = Record<string, StatusCounts>;

export type PipelineType =
  | 'cta'
  | 'tips-edu'
  | 'collec-story'
  | 'day-night-story'
  | 'moodboard-story'
  | 'product-specs'
  | 'style-this'
  | 'myth-fact-story'
  | 'product-desc-story'
  | 'this-or-that-story'
  | 'one-product-3-styles'
  | 'tips-edu-feed'
  | 'collection-feed'
  | 'moodboard-1-feed'
  | 'moodboard-2-feed'
  | 'day-night-feed'
  | 'product-showcase-feed'
  | 'product-closeup-reel'
  | 'day-night-reel'
  | 'before-after-reel'
  | 'style-reel-slideshow'
  | 'moodboard-reel'
  | 'one-product-three-styles-reel'
  | 'one-at-a-time-lights-reel'
  | 'sketch-to-draw-reel'
  | 'ad-cover'
  | 'christmas-banner'
  | 'sale-banner'
  | null;

import { useState, useEffect, useRef } from 'react';
import { toast, Toaster } from 'sonner';
import { RefreshCw, Key, X, Sparkles, Globe, Check } from 'lucide-react';
import { FormatTabs, TabType } from './components/planning/FormatTabs';
import { SubTabRail } from './components/planning/SubTabRail';
import { FixtureProgressGrid } from './components/planning/FixtureProgressGrid';
import { FixtureData } from './components/planning/FixtureCard';
import { RunConfirmModal } from './components/planning/RunConfirmModal';
import { RowInspectorModal } from './components/planning/RowInspectorModal';
import { LiveLogViewer } from './components/planning/LiveLogViewer';
import { QueueDock, QueueJob, QueueHistoryItem } from './components/planning/QueueDock';
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

const CONTENT_CONFIG: Record<TabType, { name: string; ratio: string; items: string[] }> = {
  feed: {
    name: 'Feed',
    ratio: '4:5 (1080 × 1350 px)',
    items: [
      'Tips & Educational',
      'Collection Category',
      'Moodboard #1',
      'Moodboard #2',
      '1 product, 3 styles',
      'Day & Night',
      'Product Showcase',
    ],
  },
  story: {
    name: 'Story',
    ratio: '9:16 (1080 × 1920 px)',
    items: [
      'CTA',
      'Tips & Educational',
      'Collection Category',
      'Day & Night',
      'Moodboard Story',
      'Product Closeup w/ Specifications',
      'Style This?',
      'Myth & Fact',
      'Product Closeup w/ Description',
      'This or That',
    ],
  },
  reel: {
    name: 'Reel',
    ratio: '9:16 (1080 × 1920 px)',
    items: [
      'Product Closeup',
      'Day & Night',
      'Before & After',
      'Styled Reel Slideshow',
      'Moodboard',
      '1 Product, 3 Styles',
    ],
  },
};

// The 5 CTA Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const CTA_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblYHdVq14FjMWg5o', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblfl7fqFZa2vUieB', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblSpGJLO3faYfIDY', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait' },
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblKJeCCp4zQ6g7Em', moodboardId: '351d992d-19e3-4b1e-aa46-08a842796c61', prompt: 'Generate me a modern bedroom with a table lamp side by side' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblPKSYyjgbgMypE2', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Modern living room interior, stylish lounge chair, warm ambient lighting, spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait' },
];

// The 6 Tips & Educational Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const TIPS_EDU_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblwnFN5a8fLzKuP4', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblJxWwZexgBHl26B', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate a premium modern interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp beside an armchair.' },
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblpFiaNn1Ym9fTTk', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room' },
  { id: 'ceiling-mounted', name: 'Ceiling Mounted', total: 100, tableId: 'tblGlRibUZXB9R3Gt', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate a premium modern hallway interior in a vertical 9:16 composition with clean walls and a plain flat ceiling.' },
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblZtENqILDAekLv2', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate a premium modern bedroom interior with a prominent bedside nightstand table surface.' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tbllzkE2prSyj9BaD', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate a premium modern high-ceiling living room interior with a spacious vertical ceiling volume.' },
];

// The 5 Collection Category Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const COLLECTION_CATEGORY_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblSSVJnubFk2yBm3', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room hanging pendant light not too oversize item' },
  { id: 'wall-light', name: 'Wall Lights', total: 100, tableId: 'tbl98UU0h4uFyFIlL', moodboardId: 'afa1317e-7be1-47f5-9d6f-91c7769a767d', prompt: 'Generate me a modern living room with wall sconce mounted on the wall' },
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblJMJQlrnlDb1GtN', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room hanging chandelier' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblloZLRSKwOCg247', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern bedroom that have beside a floor lamp' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblsXXcoZZD4q6WWt', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room with cluster chandelier hanging from the ceiling' },
];

// The 5 Day & Night Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const DAY_NIGHT_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblKkCf88UVQ3Yu07', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblaNyYZCR7E6TXtv', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room with plain ceiling for hanging pendant light' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblr1hlsjGcs9QKCy', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tblhvM9Saq18YqONB', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate me a modern bedroom with a bedside table for a table lamp' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblgcvB4WFKOpSIQl', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling for a cluster chandelier' },
];

// The 3 Moodboard Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const MOODBOARD_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblHQrci8d1K9ws2M', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblkm119i48y0M1IQ', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblBaNeiSZeYrUawW', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
];

// The Product Closeup w/ Specs fixtures (Chandelier + dynamic .env hooks)
const PRODUCT_SPECS_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblEGTB6BodRVDqBV' },
];

// The 2 Style This? Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const STYLE_THIS_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblYge5R7LwTJkEHC', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblvSAzXasTVI85r9', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room' },
];

// The 3 Myth & Fact Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
const MYTH_FACT_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbl3OI7crWvN2Q7u6', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblf5Yaki4ktwiLtx', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblwBnWYRGcV6as45', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
];

// The 6 Product Closeup w/ Description Story fixtures with actual Airtable Table IDs
const PRODUCT_DESCRIPTION_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblDcT6jovdAbKnfw' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblDD2w4v0Idb4jAZ' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblPvHyKGByWJCMtY' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblnIOQVywHcTgAtv' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tbl5S9JEHSrjrLwxA' },
  { id: 'wall-light', name: 'Wall Light', total: 100, tableId: 'tblYqudlgjYMNRROM' },
];

// The 6 This or That Story fixtures with actual Airtable Table IDs
const THIS_OR_THAT_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblo42IkuhYLIQBzk' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblS1VHp41RDfxztD' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblaoqj8VPVHFmVQn' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblYAhjKckXtjUayx' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tblm1Ty2QkAlUcHJt' },
  { id: 'wall-light', name: 'Wall Light', total: 100, tableId: 'tblZw6jvSa27oZDiN' },
];

// Subtab 0: Tips & Educational Feed (4:5)
const TIPS_EDU_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblQ65S51Dmauwx4c', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room hanging chandelier from the ceiling' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblIhCP3Gjg09QFCK', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblQuhvktqYB59Ofw', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblwY6eGQCD5bJeF1', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling for a cluster chandelier' },
];

// Subtab 1: Collection Category Feed (4:5)
const COLLECTION_CATEGORY_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'collection', name: '5-Room Collection', total: 100, tableId: 'tbl5o1j3XvUaUqmjs' },
];

// Subtab 2: Moodboard #1 Feed (4:5)
const MOODBOARD_1_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbl9u5vjgx8kuE44R', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblOvvYdgsNTXh2zK', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tbl6uTmwM23KK9ocO', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
];

// Subtab 3: Moodboard #2 Feed (4:5)
const MOODBOARD_2_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbltWgQKOYjuHw6tx', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tbl4TiV90SzdBz4KG', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tbl4YF9iXlBqGblEc', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'wall-light', name: 'Wall Lights', total: 100, tableId: 'tbljUk9JwzS1JeZJg', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room with a wall light' },
];

// Subtab 4: The 3 1 Product, 3 Styles Feed fixtures (4:5)
const ONE_PRODUCT_THREE_STYLES_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblRy52kCasisCWzd', moodboardId: '2a4a62bf-c6eb-49f8-8808-2543200634a0', prompt: 'Generate me a luxury modern dining room with hanging pendant light' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tbl9GIq2QeYCwMhWU', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a luxury modern living room lounge with standing floor lamp' },
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblrlfqBGe5EjS5PI', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a luxury modern grand living room with hanging chandelier' },
];

// Subtab 5: Day & Night Feed (4:5)
const DAY_NIGHT_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblSceuLVvLMQ6wWp', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblIgRlTtO7Y2EGIo', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room with plain ceiling for hanging pendant light' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblcKHAVYgzIcmabT', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tbljsKOEhc0618qbM', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate me a modern bedroom with a bedside table for a table lamp' },
];

// Subtab 6: Product Showcase Feed (4:5)
const PRODUCT_SHOWCASE_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tbln0MNBaVVrZ0wrF' },
];

// Reel Subtab 0: Product Closeup Reel (9:16)
const PRODUCT_CLOSEUP_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblqBZ946hVdOpmDV', moodboardId: 'fb2487fb-2895-4d2c-9758-805aaf1bac69', prompt: 'Generate me a modern bedroom nightstand' },
];

// Reel Subtab 1: Day & Night Reel (9:16)
const DAY_NIGHT_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblkTuM627s2f0FTN', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'chandelier', name: 'Chandeliers', total: 100, tableId: 'tbl35JySlNuWh61tL', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblVPgI4C6HEFcKW9', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
];

// Reel Subtab 2: Before & After Reel (9:16)
const BEFORE_AFTER_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tbleUP86Kw36G8Hdw', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'chandelier', name: 'Chandeliers', total: 100, tableId: 'tbloMhCOngGDWFS2y', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a photo a modern living room hanging chandelier from the ceiling' },
];

// Reel Subtab 3: Style Reel Slideshow (9:16)
const STYLE_REEL_SLIDESHOW_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'style-tour', name: '5-Room Style Tour', total: 100, tableId: 'tblFFEvkHb3jLKrcv', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate 5 coherent modern rooms for a cohesive home tour' },
];

// Reel Subtab 4: Moodboard Reel (9:16)
const MOODBOARD_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier Modern', total: 100, tableId: 'tbl026zbECJJ9FRfj', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblpjRudEy6fobIrP', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'cluster-chandelier', name: 'Cluster Chandeliers', total: 100, tableId: 'tblJX6rd5nhhEuWbL', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling for cluster chandelier' },
  { id: 'linear-chandelier', name: 'Linear Chandeliers', total: 100, tableId: 'tblj4DVzllYa8pliK', moodboardId: '994a703c-4c6b-498a-bb27-7609615a74bd', prompt: 'Modern luxury kitchen island or dining table' },
  { id: 'floor-lamp', name: 'Floor Lamps', total: 100, tableId: 'tblF3ot4fdHN2VCQn', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'wall-sconce', name: 'Wall Sconces', total: 100, tableId: 'tbli7nuOEhR8inzva', moodboardId: 'afa1317e-7be1-47f5-9d6f-91c7769a767d', prompt: 'Generate me a modern hallway or living room with wall sconce' },
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblr0uAYkDWDQZinl', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate me a modern bedroom with bedside table for a table lamp' },
];

// Reel Subtab 5: 1 Product, 3 Styles Reel (9:16)
const ONE_PRODUCT_THREE_STYLES_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbl6ls4AWcEcynBpZ', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern luxury living room with high ceiling for chandelier' },
];

const DEFAULT_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100 },
  { id: 'pendant', name: 'Pendant Lights', total: 100 },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100 },
  { id: 'table-lamp', name: 'Table Lamps', total: 100 },
];

/** Return the fixtures list for a specific format tab and subtab index. */
const getFixturesForSubtab = (tab: TabType, subtabIdx: number): Omit<FixtureData, 'completed'>[] => {
  if (tab === 'story') {
    switch (subtabIdx) {
      case 0: return CTA_STORY_FIXTURES;
      case 1: return TIPS_EDU_STORY_FIXTURES;
      case 2: return COLLECTION_CATEGORY_STORY_FIXTURES;
      case 3: return DAY_NIGHT_STORY_FIXTURES;
      case 4: return MOODBOARD_STORY_FIXTURES;
      case 5: return PRODUCT_SPECS_STORY_FIXTURES;
      case 6: return STYLE_THIS_STORY_FIXTURES;
      case 7: return MYTH_FACT_STORY_FIXTURES;
      case 8: return PRODUCT_DESCRIPTION_STORY_FIXTURES;
      case 9: return THIS_OR_THAT_STORY_FIXTURES;
      default: return DEFAULT_FIXTURES;
    }
  }
  if (tab === 'feed') {
    switch (subtabIdx) {
      case 0: return TIPS_EDU_FEED_FIXTURES;
      case 1: return COLLECTION_CATEGORY_FEED_FIXTURES;
      case 2: return MOODBOARD_1_FEED_FIXTURES;
      case 3: return MOODBOARD_2_FEED_FIXTURES;
      case 4: return ONE_PRODUCT_THREE_STYLES_FIXTURES;
      case 5: return DAY_NIGHT_FEED_FIXTURES;
      case 6: return PRODUCT_SHOWCASE_FEED_FIXTURES;
      default: return DEFAULT_FIXTURES;
    }
  }
  if (tab === 'reel') {
    switch (subtabIdx) {
      case 0: return PRODUCT_CLOSEUP_REEL_FIXTURES;
      case 1: return DAY_NIGHT_REEL_FIXTURES;
      case 2: return BEFORE_AFTER_REEL_FIXTURES;
      case 3: return STYLE_REEL_SLIDESHOW_FIXTURES;
      case 4: return MOODBOARD_REEL_FIXTURES;
      case 5: return ONE_PRODUCT_THREE_STYLES_REEL_FIXTURES;
      default: return DEFAULT_FIXTURES;
    }
  }
  return DEFAULT_FIXTURES;
};

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('story');
  const [activeSubTab, setActiveSubTab] = useState<number>(0);

  // Keyed by `${tab}-${subTabIndex}-${fixtureId}` so each item retains its own progress
  const [progressState, setProgressState] = useState<Record<string, number>>({});

  const [isLoadingCounts, setIsLoadingCounts] = useState<boolean>(false);
  const [confirmModalFixture, setConfirmModalFixture] = useState<FixtureData | null>(null);
  const [isStartingRun, setIsStartingRun] = useState<boolean>(false);
  const [studioPin, setStudioPin] = useState<string>(() => localStorage.getItem('hc_studio_pin') || '');
  const [showPinModal, setShowPinModal] = useState<boolean>(false);
  const [pinInput, setPinInput] = useState<string>('');
  const [tunnelInfo, setTunnelInfo] = useState<{ active: boolean; public_url: string }>({ active: false, public_url: '' });
  const [runningPipelineType, setRunningPipelineType] = useState<
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
    | null
  >(null);

  // Unified FIFO Generation Queue states
  const [activeQueueJob, setActiveQueueJob] = useState<QueueJob | null>(null);
  const [pendingQueue, setPendingQueue] = useState<QueueJob[]>([]);
  const [queueHistory, setQueueHistory] = useState<QueueHistoryItem[]>([]);

  // Krea Moodboard states for all Story and Feed pipelines that generate room interiors
  const [oneProductThreeStylesMoodboards, setOneProductThreeStylesMoodboards] = useState<Record<string, string>>({
    'pendant': '2a4a62bf-c6eb-49f8-8808-2543200634a0',
    'floor-lamp': 'b1641228-beec-4823-8d01-1de3eec8410d',
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
  });
  const [tipsEduFeedMoodboards, setTipsEduFeedMoodboards] = useState<Record<string, string>>({
    'chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
    'pendant': 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3',
    'floor-lamp': 'b1641228-beec-4823-8d01-1de3eec8410d',
    'cluster-chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
  });
  const [mb1FeedMoodboards, setMb1FeedMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
  });
  const [mb2FeedMoodboards, setMb2FeedMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
    'wall-light': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
  });
  const [dayNightFeedMoodboards, setDayNightFeedMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
    'table-lamp': '257569e1-7be8-4412-a90f-acbc347e4646',
  });
  const [ctaMoodboards, setCtaMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
    'cluster-chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
    'table-lamp': '351d992d-19e3-4b1e-aa46-08a842796c61',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
  });
  const [tipsMoodboards, setTipsMoodboards] = useState<Record<string, string>>({
    'pendant': 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3',
    'floor-lamp': 'b1641228-beec-4823-8d01-1de3eec8410d',
    'chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
    'ceiling-mounted': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
    'table-lamp': '257569e1-7be8-4412-a90f-acbc347e4646',
    'cluster-chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
  });
  const [collecMoodboards, setCollecMoodboards] = useState<Record<string, string>>({
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
    'wall-light': 'afa1317e-7be1-47f5-9d6f-91c7769a767d',
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
    'cluster-chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
  });
  const [dayNightMoodboards, setDayNightMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'pendant': 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
    'table-lamp': '257569e1-7be8-4412-a90f-acbc347e4646',
    'cluster-chandelier': 'b5ffdcbb-192e-4528-8d86-d1a4cf496887',
  });
  const [moodboardMoodboards, setMoodboardMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
  });
  const [styleMoodboards, setStyleMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
  });
  const [mythFactMoodboards, setMythFactMoodboards] = useState<Record<string, string>>({
    'chandelier': 'de6ad512-870d-4ab7-a48c-3f3ca85faf24',
    'floor-lamp': 'c4c15a18-a92d-4465-924f-c85cfe1958bc',
    'pendant': '0844ad92-c34a-4dc8-9d70-d09498dc098c',
  });
  const [editMoodboardFixture, setEditMoodboardFixture] = useState<FixtureData | null>(null);
  const [editMoodboardInput, setEditMoodboardInput] = useState<string>('');
  const [isSavingMoodboard, setIsSavingMoodboard] = useState<boolean>(false);

  // Krea Prompt states for all Story pipelines
  const [ctaPrompts, setCtaPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room',
    'cluster-chandelier': 'Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait',
    'table-lamp': 'Generate me a modern bedroom with a table lamp side by side',
    'floor-lamp': 'Modern living room interior, stylish lounge chair, warm ambient lighting, spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait',
  });
  const [tipsPrompts, setTipsPrompts] = useState<Record<string, string>>({
    'pendant': 'Generate me a modern dining room',
    'floor-lamp': 'Generate a premium modern interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp beside an armchair.',
    'chandelier': 'Generate me a modern living room',
    'ceiling-mounted': 'Generate a premium modern hallway interior in a vertical 9:16 composition with clean walls and a plain flat ceiling.',
    'table-lamp': 'Generate a premium modern bedroom interior with a prominent bedside nightstand table surface.',
    'cluster-chandelier': 'Generate a premium modern high-ceiling living room interior with a spacious vertical ceiling volume.',
  });
  const [collecPrompts, setCollecPrompts] = useState<Record<string, string>>({
    'pendant': 'Generate me a modern dining room hanging pendant light not too oversize item',
    'wall-light': 'Generate me a modern living room with wall sconce mounted on the wall',
    'chandelier': 'Generate me a modern living room hanging chandelier',
    'floor-lamp': 'Generate me a modern bedroom that have beside a floor lamp',
    'cluster-chandelier': 'Generate me a modern living room with cluster chandelier hanging from the ceiling',
  });
  const [dayNightPrompts, setDayNightPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room with plain ceiling for hanging pendant light',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
    'table-lamp': 'Generate me a modern bedroom with a bedside table for a table lamp',
    'cluster-chandelier': 'Generate me a luxury modern room with high ceiling for a cluster chandelier',
  });
  const [moodboardPrompts, setMoodboardPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
  });
  const [stylePrompts, setStylePrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'floor-lamp': 'Generate me a modern living room',
  });
  const [mythFactPrompts, setMythFactPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'floor-lamp': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room',
  });
  const [tipsEduFeedPrompts, setTipsEduFeedPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room hanging chandelier from the ceiling',
    'pendant': 'Generate me a modern dining room',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
    'cluster-chandelier': 'Generate me a luxury modern room with high ceiling for a cluster chandelier',
  });
  const [mb1FeedPrompts, setMb1FeedPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
  });
  const [mb2FeedPrompts, setMb2FeedPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
    'wall-light': 'Generate me a modern living room with a wall light',
  });
  const [dayNightFeedPrompts, setDayNightFeedPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room with plain ceiling for hanging pendant light',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
    'table-lamp': 'Generate me a modern bedroom with a bedside table for a table lamp',
  });
  const [oneProductThreeStylesPrompts, setOneProductThreeStylesPrompts] = useState<Record<string, string>>({
    'pendant': 'Generate me a luxury modern dining room with hanging pendant light',
    'floor-lamp': 'Generate me a luxury modern living room lounge with standing floor lamp',
    'chandelier': 'Generate me a luxury modern grand living room with hanging chandelier',
  });
  const [editPromptFixture, setEditPromptFixture] = useState<FixtureData | null>(null);
  const [editPromptInput, setEditPromptInput] = useState<string>('');
  const [isSavingPrompt, setIsSavingPrompt] = useState<boolean>(false);

  // Status breakdown counts (P, S, C, D, FM) for all pipelines
  type StatusCountMap = Record<string, { P: number; S?: number; C: number; D: number; FM: number }>;
  const [oneProductThreeStylesStatusCounts, setOneProductThreeStylesStatusCounts] = useState<StatusCountMap>({});
  const [tipsEduFeedStatusCounts, setTipsEduFeedStatusCounts] = useState<StatusCountMap>({});
  const [collecFeedStatusCounts, setCollecFeedStatusCounts] = useState<StatusCountMap>({});
  const [mb1FeedStatusCounts, setMb1FeedStatusCounts] = useState<StatusCountMap>({});
  const [mb2FeedStatusCounts, setMb2FeedStatusCounts] = useState<StatusCountMap>({});
  const [dayNightFeedStatusCounts, setDayNightFeedStatusCounts] = useState<StatusCountMap>({});
  const [prodShowcaseFeedStatusCounts, setProdShowcaseFeedStatusCounts] = useState<StatusCountMap>({});
  const [ctaStatusCounts, setCtaStatusCounts] = useState<StatusCountMap>({});
  const [tipsStatusCounts, setTipsStatusCounts] = useState<StatusCountMap>({});
  const [collecStatusCounts, setCollecStatusCounts] = useState<StatusCountMap>({});
  const [dayNightStatusCounts, setDayNightStatusCounts] = useState<StatusCountMap>({});
  const [moodboardStatusCounts, setMoodboardStatusCounts] = useState<StatusCountMap>({});
  const [productSpecsStatusCounts, setProductSpecsStatusCounts] = useState<StatusCountMap>({});
  const [styleThisStatusCounts, setStyleThisStatusCounts] = useState<StatusCountMap>({});
  const [mythFactStatusCounts, setMythFactStatusCounts] = useState<StatusCountMap>({});
  const [productDescStatusCounts, setProductDescStatusCounts] = useState<StatusCountMap>({});
  const [thisOrThatStatusCounts, setThisOrThatStatusCounts] = useState<StatusCountMap>({});

  const [productCloseupReelMoodboards, setProductCloseupReelMoodboards] = useState<Record<string, string>>({});
  const [productCloseupReelPrompts, setProductCloseupReelPrompts] = useState<Record<string, string>>({
    'table-lamp': 'Generate me a modern bedroom nightstand',
  });
  const [dayNightReelMoodboards, setDayNightReelMoodboards] = useState<Record<string, string>>({});
  const [dayNightReelPrompts, setDayNightReelPrompts] = useState<Record<string, string>>({
    'pendant': 'Generate me a modern dining room',
    'chandelier': 'Generate me a modern living room',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
  });
  const [beforeAfterReelMoodboards, setBeforeAfterReelMoodboards] = useState<Record<string, string>>({});
  const [beforeAfterReelPrompts, setBeforeAfterReelPrompts] = useState<Record<string, string>>({
    'floor-lamp': 'Generate me a bedroom that have beside a floor lamp',
    'pendant': 'Generate me a modern dining room',
    'chandelier': 'Generate me a photo a modern living room hanging chandelier from the ceiling',
  });
  const [styleReelMoodboards, setStyleReelMoodboards] = useState<Record<string, string>>({});
  const [styleReelPrompts, setStyleReelPrompts] = useState<Record<string, string>>({
    'style-tour': 'Generate 5 coherent modern rooms for a cohesive home tour',
  });
  const [moodboardReelMoodboards, setMoodboardReelMoodboards] = useState<Record<string, string>>({});
  const [moodboardReelPrompts, setMoodboardReelPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern living room',
    'pendant': 'Generate me a modern dining room',
    'cluster-chandelier': 'Generate me a luxury modern room with high ceiling for cluster chandelier',
    'linear-chandelier': 'Modern luxury kitchen island or dining table',
    'floor-lamp': 'Generate me a modern living room with empty floor space for a standing floor lamp',
    'wall-sconce': 'Generate me a modern hallway or living room with wall sconce',
    'table-lamp': 'Generate me a modern bedroom with bedside table for a table lamp',
  });
  const [oneProductThreeStylesReelMoodboards, setOneProductThreeStylesReelMoodboards] = useState<Record<string, string>>({});
  const [oneProductThreeStylesReelPrompts, setOneProductThreeStylesReelPrompts] = useState<Record<string, string>>({
    'chandelier': 'Generate me a modern luxury living room with high ceiling for chandelier',
  });

  const [productCloseupReelStatusCounts, setProductCloseupReelStatusCounts] = useState<StatusCountMap>({});
  const [dayNightReelStatusCounts, setDayNightReelStatusCounts] = useState<StatusCountMap>({});
  const [beforeAfterReelStatusCounts, setBeforeAfterReelStatusCounts] = useState<StatusCountMap>({});
  const [styleReelStatusCounts, setStyleReelStatusCounts] = useState<StatusCountMap>({});
  const [moodboardReelStatusCounts, setMoodboardReelStatusCounts] = useState<StatusCountMap>({});
  const [oneProductThreeStylesReelStatusCounts, setOneProductThreeStylesReelStatusCounts] = useState<StatusCountMap>({});

  // Row Inspector Modal state
  const [inspectFixture, setInspectFixture] = useState<FixtureData | null>(null);
  const [inspectStatusFilter, setInspectStatusFilter] = useState<string>('all');

  const handleOpenRowInspector = (fixture: FixtureData, statusFilter: string = 'all') => {
    setInspectFixture(fixture);
    setInspectStatusFilter(statusFilter);
  };

  const [tipsTableIds, setTipsTableIds] = useState<Record<string, string>>({});

  const [pipelineState, setPipelineState] = useState<PipelineExecutionState>({
    status: 'idle',
    active_fixture: null,
    active_table_id: null,
    current_phase: '',
    current_phase_index: 0,
    total_phases: 6,
    elapsed_seconds: 0,
    logs: [],
  });

  const isCtaStoryActive = activeTab === 'story' && activeSubTab === 0;
  const isTipsEduStoryActive = activeTab === 'story' && activeSubTab === 1;
  const isCollecCatStoryActive = activeTab === 'story' && activeSubTab === 2;
  const isDayNightStoryActive = activeTab === 'story' && activeSubTab === 3;
  const isMoodboardStoryActive = activeTab === 'story' && activeSubTab === 4;
  const isProductSpecsStoryActive = activeTab === 'story' && activeSubTab === 5;
  const isStyleThisStoryActive = activeTab === 'story' && activeSubTab === 6;
  const isMythFactStoryActive = activeTab === 'story' && activeSubTab === 7;
  const isProductDescStoryActive = activeTab === 'story' && activeSubTab === 8;
  const isThisOrThatStoryActive = activeTab === 'story' && activeSubTab === 9;

  const isTipsEduFeedActive = activeTab === 'feed' && activeSubTab === 0;
  const isCollecCatFeedActive = activeTab === 'feed' && activeSubTab === 1;
  const isMoodboard1FeedActive = activeTab === 'feed' && activeSubTab === 2;
  const isMoodboard2FeedActive = activeTab === 'feed' && activeSubTab === 3;
  const isOneProductThreeStylesFeedActive = activeTab === 'feed' && activeSubTab === 4;
  const isDayNightFeedActive = activeTab === 'feed' && activeSubTab === 5;
  const isProductShowcaseFeedActive = activeTab === 'feed' && activeSubTab === 6;

  const isProductCloseupReelActive = activeTab === 'reel' && activeSubTab === 0;
  const isDayNightReelActive = activeTab === 'reel' && activeSubTab === 1;
  const isBeforeAfterReelActive = activeTab === 'reel' && activeSubTab === 2;
  const isStyleReelActive = activeTab === 'reel' && activeSubTab === 3;
  const isMoodboardReelActive = activeTab === 'reel' && activeSubTab === 4;
  const isOneProductThreeStylesReelActive = activeTab === 'reel' && activeSubTab === 5;

  const isInteractivePipelineActive = activeTab === 'story' || activeTab === 'feed' || activeTab === 'reel';
  const activeFormat = CONTENT_CONFIG[activeTab];

  const getActivePipelineConfig = () => {
    if (isCtaStoryActive) {
      return {
        type: 'cta' as const,
        name: 'CTA Story',
        runEndpoint: '/api/cta/run',
        statusEndpoint: '/api/cta/status',
        stopEndpoint: '/api/cta/stop',
        totalPhases: 6,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interior ➔ Claude Prompt ➔ Banana Blend ➔ Headline ➔ Layout Stamping',
        subtabIndex: 0,
      };
    }
    if (isTipsEduStoryActive) {
      return {
        type: 'tips-edu' as const,
        name: 'Tips & Educational Story',
        runEndpoint: '/api/tips-edu/run',
        statusEndpoint: '/api/tips-edu/status',
        stopEndpoint: '/api/tips-edu/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interior ➔ Claude Prompt ➔ Banana Blend ➔ Layout Stamping',
        subtabIndex: 1,
      };
    }
    if (isCollecCatStoryActive) {
      return {
        type: 'collec-story' as const,
        name: 'Collection Category Story',
        runEndpoint: '/api/collection-story/run',
        statusEndpoint: '/api/collection-story/status',
        stopEndpoint: '/api/collection-story/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interiors (3 slots) ➔ Claude Prompts ➔ Banana Blend (3 slots) ➔ 9:16 Grid & Overlays',
        subtabIndex: 2,
      };
    }
    if (isDayNightStoryActive) {
      return {
        type: 'day-night-story' as const,
        name: 'Day & Night Story',
        runEndpoint: '/api/day-night-story/run',
        statusEndpoint: '/api/day-night-story/status',
        stopEndpoint: '/api/day-night-story/stop',
        totalPhases: 4,
        phaseSummary: 'Akeneo Scrape ➔ Krea AI Interior ➔ Claude Sonnet 5 Prompt ➔ Nano Banana Pro Day & Night Blending + Logo',
        subtabIndex: 3,
      };
    }
    if (isMoodboardStoryActive) {
      return {
        type: 'moodboard-story' as const,
        name: 'Moodboard Story',
        runEndpoint: '/api/moodboard-story/run',
        statusEndpoint: '/api/moodboard-story/status',
        stopEndpoint: '/api/moodboard-story/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea AI Interior ➔ Claude Sonnet 5 Prompt ➔ Banana Daytime Blend ➔ Logo ➔ Moodboard Card',
        subtabIndex: 4,
      };
    }
    if (isProductSpecsStoryActive) {
      return {
        type: 'product-specs' as const,
        name: 'Product Closeup w/ Specs Story',
        runEndpoint: '/api/product-specs/run',
        statusEndpoint: '/api/product-specs/status',
        stopEndpoint: '/api/product-specs/stop',
        totalPhases: 2,
        phaseSummary: 'Akeneo Product Scrape & Specs Layout ➔ Nano Banana Pro 9:16 Blending & Airtable Upload',
        subtabIndex: 5,
      };
    }
    if (isStyleThisStoryActive) {
      return {
        type: 'style-this' as const,
        name: 'Style This? Story',
        runEndpoint: '/api/style-this/run',
        statusEndpoint: '/api/style-this/status',
        stopEndpoint: '/api/style-this/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interiors (4 slots) ➔ Claude Vision & Color ➔ Banana Blend ➔ Double-Tap & Pill Stamping',
        subtabIndex: 6,
      };
    }
    if (isMythFactStoryActive) {
      return {
        type: 'myth-fact-story' as const,
        name: 'Myth & Fact Story',
        runEndpoint: '/api/myth-fact-story/run',
        statusEndpoint: '/api/myth-fact-story/status',
        stopEndpoint: '/api/myth-fact-story/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interiors ➔ Claude Prompts ➔ Debunk Cover ➔ Myth & Fact Blends ➔ Outro Slide & Upload',
        subtabIndex: 7,
      };
    }
    if (isProductDescStoryActive) {
      return {
        type: 'product-desc-story' as const,
        name: 'Product Closeup w/ Description Story',
        runEndpoint: '/api/product-description-story/run',
        statusEndpoint: '/api/product-description-story/status',
        stopEndpoint: '/api/product-description-story/stop',
        totalPhases: 2,
        phaseSummary: 'Akeneo Product Scrape & Description Layout ➔ Fal AI Nano Banana Pro 9:16 Description Card Blending',
        subtabIndex: 8,
      };
    }
    if (isThisOrThatStoryActive) {
      return {
        type: 'this-or-that-story' as const,
        name: 'This or That Story',
        runEndpoint: '/api/this-or-that/run',
        statusEndpoint: '/api/this-or-that/status',
        stopEndpoint: '/api/this-or-that/stop',
        totalPhases: 2,
        phaseSummary: 'Akeneo 2-Product Scrape & Watermark Template ➔ Fal AI Nano Banana Pro 9:16 Comparison Story Card',
        subtabIndex: 9,
      };
    }
    if (isTipsEduFeedActive) {
      return {
        type: 'tips-edu-feed' as const,
        name: 'Tips & Educational Feed',
        runEndpoint: '/api/tips-edu-feed/run',
        statusEndpoint: '/api/tips-edu-feed/status',
        stopEndpoint: '/api/tips-edu-feed/stop',
        totalPhases: 6,
        phaseSummary: 'Akeneo Scrape ➔ Krea 3 Interiors + Thumbnail ➔ Claude Vision Prompts ➔ Nano Banana Room Blends ➔ YOLO Item Tagging ➔ Final 3-Slide Layouts',
        subtabIndex: 0,
      };
    }
    if (isCollecCatFeedActive) {
      return {
        type: 'collection-feed' as const,
        name: 'Collection Category Feed',
        runEndpoint: '/api/collection-feed/run',
        statusEndpoint: '/api/collection-feed/status',
        stopEndpoint: '/api/collection-feed/stop',
        totalPhases: 5,
        phaseSummary: '5-Room Krea Generation ➔ Claude Room Matching ➔ Targeted Akeneo Catalog Scraper ➔ Blending Prompt Engineering ➔ Nano Banana Pro 5-Slide Blending',
        subtabIndex: 1,
      };
    }
    if (isMoodboard1FeedActive) {
      return {
        type: 'moodboard-1-feed' as const,
        name: 'Moodboard #1 Feed',
        runEndpoint: '/api/moodboard-1-feed/run',
        statusEndpoint: '/api/moodboard-1-feed/status',
        stopEndpoint: '/api/moodboard-1-feed/stop',
        totalPhases: 6,
        phaseSummary: 'Krea Interior ➔ Claude Prompting ➔ Nano Banana Pro Blending + YOLO Item Tagging ➔ Local Brand Logo ➔ Material Swatch Moodboard ➔ Macro Close-up',
        subtabIndex: 2,
      };
    }
    if (isMoodboard2FeedActive) {
      return {
        type: 'moodboard-2-feed' as const,
        name: 'Moodboard #2 Feed',
        runEndpoint: '/api/moodboard-2-feed/run',
        statusEndpoint: '/api/moodboard-2-feed/status',
        stopEndpoint: '/api/moodboard-2-feed/stop',
        totalPhases: 5,
        phaseSummary: 'Krea Interior ➔ Claude Prompt ➔ Nano Banana Pro Blending ➔ Reference Auto-Attach ➔ Editorial Flat-Lay Conversion',
        subtabIndex: 3,
      };
    }
    if (isOneProductThreeStylesFeedActive) {
      return {
        type: 'one-product-3-styles' as const,
        name: '1 Product, 3 Styles Feed',
        runEndpoint: '/api/one-product-3-styles/run',
        statusEndpoint: '/api/one-product-3-styles/status',
        stopEndpoint: '/api/one-product-3-styles/stop',
        totalPhases: 4,
        phaseSummary: 'Akeneo Scrape (Shopify Dedup) ➔ Krea 3 Interiors ➔ Claude Prompt Analysis ➔ Nano Banana Pro Multi-Blend + Logo',
        subtabIndex: 4,
      };
    }
    if (isDayNightFeedActive) {
      return {
        type: 'day-night-feed' as const,
        name: 'Day & Night Feed',
        runEndpoint: '/api/day-night-feed/run',
        statusEndpoint: '/api/day-night-feed/status',
        stopEndpoint: '/api/day-night-feed/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scraper ➔ Krea 4:5 Interior ➔ Claude Prompt Analysis ➔ Daytime Room Blending ➔ Night Transformation',
        subtabIndex: 5,
      };
    }
    if (isProductShowcaseFeedActive) {
      return {
        type: 'product-showcase-feed' as const,
        name: 'Product Showcase Feed',
        runEndpoint: '/api/product-showcase-feed/run',
        statusEndpoint: '/api/product-showcase-feed/status',
        stopEndpoint: '/api/product-showcase-feed/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape 3 Active Items ➔ 3-Podium Group Slide ➔ 3 Solo Showcase Slides ➔ Final 4-Slide Assembly',
        subtabIndex: 6,
      };
    }
    if (isProductCloseupReelActive) {
      return {
        type: 'product-closeup-reel' as const,
        name: 'Product Closeup Reel',
        runEndpoint: '/api/product-closeup-reel/run',
        statusEndpoint: '/api/product-closeup-reel/status',
        stopEndpoint: '/api/product-closeup-reel/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interior ➔ Claude Prompt ➔ Banana Blend ➔ FFmpeg Video Reel',
        subtabIndex: 0,
      };
    }
    if (isDayNightReelActive) {
      return {
        type: 'day-night-reel' as const,
        name: 'Day & Night Reel',
        runEndpoint: '/api/day-night-reel/run',
        statusEndpoint: '/api/day-night-reel/status',
        stopEndpoint: '/api/day-night-reel/stop',
        totalPhases: 7,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interior ➔ Claude Vision ➔ Banana Blend ➔ Grok Video ➔ Audio ➔ FFmpeg Concat',
        subtabIndex: 1,
      };
    }
    if (isBeforeAfterReelActive) {
      return {
        type: 'before-after-reel' as const,
        name: 'Before & After Reel',
        runEndpoint: '/api/before-after-reel/run',
        statusEndpoint: '/api/before-after-reel/status',
        stopEndpoint: '/api/before-after-reel/stop',
        totalPhases: 6,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interior ➔ Claude Vision ➔ Banana Blend ➔ Multiple Angles ➔ FFmpeg Slideshow',
        subtabIndex: 2,
      };
    }
    if (isStyleReelActive) {
      return {
        type: 'style-reel-slideshow' as const,
        name: 'Style Reel Slideshow',
        runEndpoint: '/api/style-reel-slideshow/run',
        statusEndpoint: '/api/style-reel-slideshow/status',
        stopEndpoint: '/api/style-reel-slideshow/stop',
        totalPhases: 5,
        phaseSummary: 'Multi-Category Scrape ➔ Sequential Krea Interiors ➔ Claude Vision ➔ Banana Blend ➔ FFmpeg Slideshow',
        subtabIndex: 3,
      };
    }
    if (isMoodboardReelActive) {
      return {
        type: 'moodboard-reel' as const,
        name: 'Moodboard Reel',
        runEndpoint: '/api/moodboard-reel/run',
        statusEndpoint: '/api/moodboard-reel/status',
        stopEndpoint: '/api/moodboard-reel/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea Interiors ➔ Claude Vision ➔ Banana Blend ➔ Template Conversion & Video Reel',
        subtabIndex: 4,
      };
    }
    if (isOneProductThreeStylesReelActive) {
      return {
        type: 'one-product-three-styles-reel' as const,
        name: '1 Product, 3 Styles Reel',
        runEndpoint: '/api/one-product-3-styles-reel/run',
        statusEndpoint: '/api/one-product-3-styles-reel/status',
        stopEndpoint: '/api/one-product-3-styles-reel/stop',
        totalPhases: 5,
        phaseSummary: 'Akeneo Scrape ➔ Krea 9:16 Interiors ➔ Claude Vision ➔ Banana Blend ➔ YOLO Tagging ➔ Silent Reel MP4',
        subtabIndex: 5,
      };
    }
    return null;
  };

  // Fetch live counts from Airtable backend for all interactive Story pipelines
  const fetchLiveCounts = async (showToast = false) => {
    setIsLoadingCounts(true);
    try {
      const updates: Record<string, number> = {};

      const [
        ctaRes, tipsRes, collecRes, dayNightRes, mbRes, specsRes, styleRes, mfRes, prodDescRes, totRes,
        oneProdRes, tipsEduFeedRes, collecFeedRes, mb1FeedRes, mb2FeedRes, dayNightFeedRes, prodShowcaseFeedRes,
        prodCloseupReelRes, dayNightReelRes, beforeAfterReelRes, styleReelRes, mbReelRes, oneProdReelRes,
        tunnelStatusRes
      ] = await Promise.all([
        fetch('/api/cta/counts?refresh=true').catch(() => null),
        fetch('/api/tips-edu/counts?refresh=true').catch(() => null),
        fetch('/api/collection-story/counts?refresh=true').catch(() => null),
        fetch('/api/day-night-story/counts?refresh=true').catch(() => null),
        fetch('/api/moodboard-story/counts?refresh=true').catch(() => null),
        fetch('/api/product-specs/counts?refresh=true').catch(() => null),
        fetch('/api/style-this/counts?refresh=true').catch(() => null),
        fetch('/api/myth-fact-story/counts?refresh=true').catch(() => null),
        fetch('/api/product-description-story/counts?refresh=true').catch(() => null),
        fetch('/api/this-or-that/counts?refresh=true').catch(() => null),
        fetch('/api/one-product-3-styles/counts?refresh=true').catch(() => null),
        fetch('/api/tips-edu-feed/counts?refresh=true').catch(() => null),
        fetch('/api/collection-feed/counts?refresh=true').catch(() => null),
        fetch('/api/moodboard-1-feed/counts?refresh=true').catch(() => null),
        fetch('/api/moodboard-2-feed/counts?refresh=true').catch(() => null),
        fetch('/api/day-night-feed/counts?refresh=true').catch(() => null),
        fetch('/api/product-showcase-feed/counts?refresh=true').catch(() => null),
        fetch('/api/product-closeup-reel/counts?refresh=true').catch(() => null),
        fetch('/api/day-night-reel/counts?refresh=true').catch(() => null),
        fetch('/api/before-after-reel/counts?refresh=true').catch(() => null),
        fetch('/api/style-reel-slideshow/counts?refresh=true').catch(() => null),
        fetch('/api/moodboard-reel/counts?refresh=true').catch(() => null),
        fetch('/api/one-product-3-styles-reel/counts?refresh=true').catch(() => null),
        fetch('/api/tunnel/status').catch(() => null),
      ]);

      if (tunnelStatusRes && tunnelStatusRes.ok) {
        try {
          const tData = await tunnelStatusRes.json();
          setTunnelInfo({ active: Boolean(tData.active), public_url: tData.public_url || '' });
        } catch {
          // ignore
        }
      }

      if (ctaRes && ctaRes.ok) {
        const data = await ctaRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-0-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setCtaMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setCtaPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setCtaStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (tipsRes && tipsRes.ok) {
        const data = await tipsRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          const tblUpdates: Record<string, string> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-1-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
            if (fix.table_id) tblUpdates[key] = fix.table_id;
          });
          if (Object.keys(mbUpdates).length > 0) setTipsMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setTipsPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setTipsStatusCounts(prev => ({ ...prev, ...statusUpdates }));
          if (Object.keys(tblUpdates).length > 0) setTipsTableIds(prev => ({ ...prev, ...tblUpdates }));
        }
      }

      if (collecRes && collecRes.ok) {
        const data = await collecRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-2-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setCollecMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setCollecPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setCollecStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (dayNightRes && dayNightRes.ok) {
        const data = await dayNightRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-3-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setDayNightMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setDayNightPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setDayNightStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (mbRes && mbRes.ok) {
        const data = await mbRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-4-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setMoodboardMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setMoodboardPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setMoodboardStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (specsRes && specsRes.ok) {
        const data = await specsRes.json();
        if (data.counts) {
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-5-${key}`] = fix.status_counts.C;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(statusUpdates).length > 0) setProductSpecsStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (styleRes && styleRes.ok) {
        const data = await styleRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-6-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setStyleMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setStylePrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setStyleThisStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (mfRes && mfRes.ok) {
        const data = await mfRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-7-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setMythFactMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setMythFactPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setMythFactStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (prodDescRes && prodDescRes.ok) {
        const data = await prodDescRes.json();
        if (data.counts) {
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-8-${key}`] = fix.status_counts.C;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(statusUpdates).length > 0) setProductDescStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (totRes && totRes.ok) {
        const data = await totRes.json();
        if (data.counts) {
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`story-9-${key}`] = fix.status_counts.C;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(statusUpdates).length > 0) setThisOrThatStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (oneProdRes && oneProdRes.ok) {
        const data = await oneProdRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-4-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setOneProductThreeStylesMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setOneProductThreeStylesPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setOneProductThreeStylesStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (tipsEduFeedRes && tipsEduFeedRes.ok) {
        const data = await tipsEduFeedRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-0-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setTipsEduFeedMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setTipsEduFeedPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setTipsEduFeedStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (collecFeedRes && collecFeedRes.ok) {
        const data = await collecFeedRes.json();
        if (data.counts) {
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-1-${key}`] = fix.status_counts.C;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(statusUpdates).length > 0) setCollecFeedStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (mb1FeedRes && mb1FeedRes.ok) {
        const data = await mb1FeedRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-2-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setMb1FeedMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setMb1FeedPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setMb1FeedStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (mb2FeedRes && mb2FeedRes.ok) {
        const data = await mb2FeedRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-3-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setMb2FeedMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setMb2FeedPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setMb2FeedStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (dayNightFeedRes && dayNightFeedRes.ok) {
        const data = await dayNightFeedRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-5-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setDayNightFeedMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setDayNightFeedPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setDayNightFeedStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (prodShowcaseFeedRes && prodShowcaseFeedRes.ok) {
        const data = await prodShowcaseFeedRes.json();
        if (data.counts) {
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`feed-6-${key}`] = fix.status_counts.C;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(statusUpdates).length > 0) setProdShowcaseFeedStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (prodCloseupReelRes && prodCloseupReelRes.ok) {
        const data = await prodCloseupReelRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`reel-0-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setProductCloseupReelMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setProductCloseupReelPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setProductCloseupReelStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (dayNightReelRes && dayNightReelRes.ok) {
        const data = await dayNightReelRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`reel-1-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setDayNightReelMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setDayNightReelPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setDayNightReelStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (beforeAfterReelRes && beforeAfterReelRes.ok) {
        const data = await beforeAfterReelRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`reel-2-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setBeforeAfterReelMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setBeforeAfterReelPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setBeforeAfterReelStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (styleReelRes && styleReelRes.ok) {
        const data = await styleReelRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`reel-3-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setStyleReelMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setStyleReelPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setStyleReelStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (mbReelRes && mbReelRes.ok) {
        const data = await mbReelRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`reel-4-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setMoodboardReelMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setMoodboardReelPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setMoodboardReelStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (oneProdReelRes && oneProdReelRes.ok) {
        const data = await oneProdReelRes.json();
        if (data.counts) {
          const mbUpdates: Record<string, string> = {};
          const prUpdates: Record<string, string> = {};
          const statusUpdates: Record<string, { P: number; S?: number; C: number; D: number; FM: number }> = {};
          Object.entries(data.counts).forEach(([key, fix]: [string, any]) => {
            if (typeof fix.status_counts?.C === 'number') updates[`reel-5-${key}`] = fix.status_counts.C;
            if (fix.moodboard_id) mbUpdates[key] = fix.moodboard_id;
            if (fix.prompt) prUpdates[key] = fix.prompt;
            if (fix.status_counts) statusUpdates[key] = fix.status_counts;
          });
          if (Object.keys(mbUpdates).length > 0) setOneProductThreeStylesReelMoodboards(prev => ({ ...prev, ...mbUpdates }));
          if (Object.keys(prUpdates).length > 0) setOneProductThreeStylesReelPrompts(prev => ({ ...prev, ...prUpdates }));
          if (Object.keys(statusUpdates).length > 0) setOneProductThreeStylesReelStatusCounts(prev => ({ ...prev, ...statusUpdates }));
        }
      }

      if (Object.keys(updates).length > 0) {
        setProgressState(prev => ({ ...prev, ...updates }));
        if (showToast) {
          toast.success('Airtable completion counts synchronized');
        }
      }
    } catch (err) {
      console.warn('Could not fetch Airtable counts from API bridge:', err);
    } finally {
      setIsLoadingCounts(false);
    }
  };

  // Fetch Airtable counts and check backend running status on mount
  useEffect(() => {
    fetchLiveCounts();

    const checkInitialRunning = async () => {
      try {
        const [
          ctaRes, tipsRes, collecRes, dayNightRes, mbRes, specsRes, styleRes, mfRes, prodDescRes, totRes, oneProdRes,
          tipsEduFeedRes, collecFeedRes, mb1FeedRes, mb2FeedRes, dayNightFeedRes, prodShowcaseFeedRes,
          prodCloseupReelRes, dayNightReelRes, beforeAfterReelRes, styleReelRes, mbReelRes, oneProdReelRes
        ] = await Promise.all([
          fetch('/api/cta/status').catch(() => null),
          fetch('/api/tips-edu/status').catch(() => null),
          fetch('/api/collection-story/status').catch(() => null),
          fetch('/api/day-night-story/status').catch(() => null),
          fetch('/api/moodboard-story/status').catch(() => null),
          fetch('/api/product-specs/status').catch(() => null),
          fetch('/api/style-this/status').catch(() => null),
          fetch('/api/myth-fact-story/status').catch(() => null),
          fetch('/api/product-description-story/status').catch(() => null),
          fetch('/api/this-or-that/status').catch(() => null),
          fetch('/api/one-product-3-styles/status').catch(() => null),
          fetch('/api/tips-edu-feed/status').catch(() => null),
          fetch('/api/collection-feed/status').catch(() => null),
          fetch('/api/moodboard-1-feed/status').catch(() => null),
          fetch('/api/moodboard-2-feed/status').catch(() => null),
          fetch('/api/day-night-feed/status').catch(() => null),
          fetch('/api/product-showcase-feed/status').catch(() => null),
          fetch('/api/product-closeup-reel/status').catch(() => null),
          fetch('/api/day-night-reel/status').catch(() => null),
          fetch('/api/before-after-reel/status').catch(() => null),
          fetch('/api/style-reel-slideshow/status').catch(() => null),
          fetch('/api/moodboard-reel/status').catch(() => null),
          fetch('/api/one-product-3-styles-reel/status').catch(() => null),
        ]);

        if (ctaRes && ctaRes.ok) {
          const data = await ctaRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('cta');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (tipsRes && tipsRes.ok) {
          const data = await tipsRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('tips-edu');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (collecRes && collecRes.ok) {
          const data = await collecRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('collec-story');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (dayNightRes && dayNightRes.ok) {
          const data = await dayNightRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('day-night-story');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (mbRes && mbRes.ok) {
          const data = await mbRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('moodboard-story');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (specsRes && specsRes.ok) {
          const data = await specsRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('product-specs');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (styleRes && styleRes.ok) {
          const data = await styleRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('style-this');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (mfRes && mfRes.ok) {
          const data = await mfRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('myth-fact-story');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (prodDescRes && prodDescRes.ok) {
          const data = await prodDescRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('product-desc-story');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (totRes && totRes.ok) {
          const data = await totRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('this-or-that-story');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (oneProdRes && oneProdRes.ok) {
          const data = await oneProdRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('one-product-3-styles');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (tipsEduFeedRes && tipsEduFeedRes.ok) {
          const data = await tipsEduFeedRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('tips-edu-feed');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (collecFeedRes && collecFeedRes.ok) {
          const data = await collecFeedRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('collection-feed');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (mb1FeedRes && mb1FeedRes.ok) {
          const data = await mb1FeedRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('moodboard-1-feed');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (mb2FeedRes && mb2FeedRes.ok) {
          const data = await mb2FeedRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('moodboard-2-feed');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (dayNightFeedRes && dayNightFeedRes.ok) {
          const data = await dayNightFeedRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('day-night-feed');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (prodShowcaseFeedRes && prodShowcaseFeedRes.ok) {
          const data = await prodShowcaseFeedRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('product-showcase-feed');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (prodCloseupReelRes && prodCloseupReelRes.ok) {
          const data = await prodCloseupReelRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('product-closeup-reel');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (dayNightReelRes && dayNightReelRes.ok) {
          const data = await dayNightReelRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('day-night-reel');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (beforeAfterReelRes && beforeAfterReelRes.ok) {
          const data = await beforeAfterReelRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('before-after-reel');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (styleReelRes && styleReelRes.ok) {
          const data = await styleReelRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('style-reel-slideshow');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (mbReelRes && mbReelRes.ok) {
          const data = await mbReelRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('moodboard-reel');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
        if (oneProdReelRes && oneProdReelRes.ok) {
          const data = await oneProdReelRes.json();
          if (data.status === 'running') {
            setRunningPipelineType('one-product-three-styles-reel');
            setPipelineState(prev => ({ ...prev, ...data }));
            return;
          }
        }
      } catch (e) {
        // silent
      }
    };

    checkInitialRunning();
  }, []);

  // Poll pipeline status while it is actively running
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const checkStatus = async () => {
      let endpoint = '/api/cta/status';
      if (runningPipelineType === 'tips-edu') endpoint = '/api/tips-edu/status';
      else if (runningPipelineType === 'collec-story') endpoint = '/api/collection-story/status';
      else if (runningPipelineType === 'day-night-story') endpoint = '/api/day-night-story/status';
      else if (runningPipelineType === 'moodboard-story') endpoint = '/api/moodboard-story/status';
      else if (runningPipelineType === 'product-specs') endpoint = '/api/product-specs/status';
      else if (runningPipelineType === 'style-this') endpoint = '/api/style-this/status';
      else if (runningPipelineType === 'myth-fact-story') endpoint = '/api/myth-fact-story/status';
      else if (runningPipelineType === 'product-desc-story') endpoint = '/api/product-description-story/status';
      else if (runningPipelineType === 'this-or-that-story') endpoint = '/api/this-or-that/status';
      else if (runningPipelineType === 'one-product-3-styles') endpoint = '/api/one-product-3-styles/status';
      else if (runningPipelineType === 'tips-edu-feed') endpoint = '/api/tips-edu-feed/status';
      else if (runningPipelineType === 'collection-feed') endpoint = '/api/collection-feed/status';
      else if (runningPipelineType === 'moodboard-1-feed') endpoint = '/api/moodboard-1-feed/status';
      else if (runningPipelineType === 'moodboard-2-feed') endpoint = '/api/moodboard-2-feed/status';
      else if (runningPipelineType === 'day-night-feed') endpoint = '/api/day-night-feed/status';
      else if (runningPipelineType === 'product-showcase-feed') endpoint = '/api/product-showcase-feed/status';
      else if (runningPipelineType === 'product-closeup-reel') endpoint = '/api/product-closeup-reel/status';
      else if (runningPipelineType === 'day-night-reel') endpoint = '/api/day-night-reel/status';
      else if (runningPipelineType === 'before-after-reel') endpoint = '/api/before-after-reel/status';
      else if (runningPipelineType === 'style-reel-slideshow') endpoint = '/api/style-reel-slideshow/status';
      else if (runningPipelineType === 'moodboard-reel') endpoint = '/api/moodboard-reel/status';
      else if (runningPipelineType === 'one-product-three-styles-reel') endpoint = '/api/one-product-3-styles-reel/status';

      try {
        const res = await fetch(endpoint);
        if (res.ok) {
          const data = await res.json();
          setPipelineState(prev => {
            // Check if status transitioned to completed
            if (prev.status === 'running' && (data.status === 'completed' || data.status === 'success')) {
              setRunningPipelineType(null);
              const finishedFixtureId = data.active_fixture || prev.active_fixture;
              if (finishedFixtureId) {
                let subtabIdx = 0;
                let label = 'CTA';
                let tabPrefix = 'story';
                if (runningPipelineType === 'tips-edu') {
                  subtabIdx = 1;
                  label = 'Tips & Educational';
                } else if (runningPipelineType === 'collec-story') {
                  subtabIdx = 2;
                  label = 'Collection Category';
                } else if (runningPipelineType === 'day-night-story') {
                  subtabIdx = 3;
                  label = 'Day & Night';
                } else if (runningPipelineType === 'moodboard-story') {
                  subtabIdx = 4;
                  label = 'Moodboard Story';
                } else if (runningPipelineType === 'product-specs') {
                  subtabIdx = 5;
                  label = 'Product Closeup w/ Specs';
                } else if (runningPipelineType === 'style-this') {
                  subtabIdx = 6;
                  label = 'Style This?';
                } else if (runningPipelineType === 'myth-fact-story') {
                  subtabIdx = 7;
                  label = 'Myth & Fact';
                } else if (runningPipelineType === 'product-desc-story') {
                  subtabIdx = 8;
                  label = 'Product Closeup w/ Description';
                } else if (runningPipelineType === 'this-or-that-story') {
                  subtabIdx = 9;
                  label = 'This or That';
                } else if (runningPipelineType === 'one-product-3-styles') {
                  subtabIdx = 4;
                  label = '1 Product, 3 Styles Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'tips-edu-feed') {
                  subtabIdx = 0;
                  label = 'Tips & Educational Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'collection-feed') {
                  subtabIdx = 1;
                  label = 'Collection Category Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'moodboard-1-feed') {
                  subtabIdx = 2;
                  label = 'Moodboard #1 Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'moodboard-2-feed') {
                  subtabIdx = 3;
                  label = 'Moodboard #2 Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'day-night-feed') {
                  subtabIdx = 5;
                  label = 'Day & Night Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'product-showcase-feed') {
                  subtabIdx = 6;
                  label = 'Product Showcase Feed';
                  tabPrefix = 'feed';
                } else if (runningPipelineType === 'product-closeup-reel') {
                  subtabIdx = 0;
                  label = 'Product Closeup Reel';
                  tabPrefix = 'reel';
                } else if (runningPipelineType === 'day-night-reel') {
                  subtabIdx = 1;
                  label = 'Day & Night Reel';
                  tabPrefix = 'reel';
                } else if (runningPipelineType === 'before-after-reel') {
                  subtabIdx = 2;
                  label = 'Before & After Reel';
                  tabPrefix = 'reel';
                } else if (runningPipelineType === 'style-reel-slideshow') {
                  subtabIdx = 3;
                  label = 'Style Reel Slideshow';
                  tabPrefix = 'reel';
                } else if (runningPipelineType === 'moodboard-reel') {
                  subtabIdx = 4;
                  label = 'Moodboard Reel';
                  tabPrefix = 'reel';
                } else if (runningPipelineType === 'one-product-three-styles-reel') {
                  subtabIdx = 5;
                  label = '1 Product, 3 Styles Reel';
                  tabPrefix = 'reel';
                }

                toast.success(`${label} pipeline finished for ${finishedFixtureId}! Refreshing Airtable completion counts.`, {
                  duration: 5000,
                });
                // Re-sync with Airtable to ensure exact consistency
                setTimeout(() => fetchLiveCounts(), 2000);
              }
            } else if (prev.status === 'running' && (data.status === 'error' || data.status === 'stopped')) {
              setRunningPipelineType(null);
              if (data.status === 'error') {
                toast.error(`Pipeline encountered an error: ${data.error || 'Check console logs'}`);
              }
            }

            return {
              ...prev,
              ...data,
              status: (data.status === 'success' || data.status === 'completed') ? 'completed' : data.status,
            };
          });
        }
      } catch (err) {
        console.warn('Status poll error:', err);
      }
    };

    if (pipelineState.status === 'running') {
      statusPollRef.current = setInterval(checkStatus, 1500);
    } else if (statusPollRef.current) {
      clearInterval(statusPollRef.current);
      statusPollRef.current = null;
    }

    return () => {
      if (statusPollRef.current) {
        clearInterval(statusPollRef.current);
      }
    };
  }, [pipelineState.status, runningPipelineType]);

  // Ref to track active queue job transition
  const activeQueueJobRef = useRef<QueueJob | null>(null);

  // Unified Generation Queue Status Poller
  useEffect(() => {
    const pollQueue = async () => {
      try {
        const res = await fetch('/api/queue/status');
        if (res.ok) {
          const data = await res.json();
          const wasActive = !!activeQueueJobRef.current;
          activeQueueJobRef.current = data.active_job || null;
          setActiveQueueJob(data.active_job || null);
          setPendingQueue(data.queue || []);
          setQueueHistory(data.history || []);

          if (data.active_job) {
            setRunningPipelineType(data.active_job.pipeline_type);
            setPipelineState({
              status: 'running',
              active_fixture: data.active_job.fixture_id,
              active_table_id: data.active_job.table_id,
              current_phase: data.active_job.current_phase || 'Processing...',
              current_phase_index: data.active_job.current_phase_index || 0,
              total_phases: data.active_job.total_phases || 5,
              elapsed_seconds: data.active_job.elapsed_seconds || 0,
              logs: data.active_job.logs || [],
              error: data.active_job.error || null,
            });
          } else if (wasActive && !data.active_job) {
            // Queue job transitioned from active to completed/cleared
            setRunningPipelineType(null);
            setPipelineState(prev => ({
              ...prev,
              status: 'completed',
            }));
            setTimeout(() => fetchLiveCounts(), 1500);
          }
        }
      } catch {
        // silent fail
      }
    };

    pollQueue();
    const interval = setInterval(pollQueue, 1500);
    return () => clearInterval(interval);
  }, []);

  const getQueueInfo = (fixtureId: string) => {
    const activeType = getActivePipelineConfig()?.type;
    const idx = pendingQueue.findIndex(j => j.pipeline_type === activeType && j.fixture_id === fixtureId);
    if (idx >= 0) {
      return { isQueued: true, position: idx + 1 };
    }
    return { isQueued: false, position: 0 };
  };

  const handleCancelQueueFixture = async (fixture: FixtureData) => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/cancel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ fixture_id: fixture.id, pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || `Removed ${fixture.name} from queue`);
        setPendingQueue(prev => prev.filter(j => j.fixture_id !== fixture.id));
      } else {
        toast.error(data.error || 'Failed to cancel queued item');
      }
    } catch (err) {
      toast.error(`Error: ${err}`);
    }
  };

  const handleCancelQueueItem = async (jobId: string, fixtureName: string) => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/cancel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ job_id: jobId, pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || `Removed ${fixtureName} from queue`);
        setPendingQueue(prev => prev.filter(j => j.id !== jobId));
      } else {
        toast.error(data.error || 'Failed to cancel queued item');
      }
    } catch (err) {
      toast.error(`Error: ${err}`);
    }
  };

  const handleClearQueue = async () => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(data.message || 'Generation queue cleared');
        setPendingQueue([]);
      } else {
        toast.error(data.error || 'Failed to clear queue');
      }
    } catch (err) {
      toast.error(`Error: ${err}`);
    }
  };

  const handleStopActiveJob = async () => {
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/stop-current', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.info(data.message || 'Stop request sent');
      } else {
        await handleStopPipeline();
      }
    } catch {
      await handleStopPipeline();
    }
  };

  // Handle clicking "Run" on a fixture card
  const handleOpenRunModal = (fixture: FixtureData) => {
    let dynMoodboard = fixture.moodboardId;
    let dynPrompt = fixture.prompt;
    if (isCtaStoryActive) {
      dynMoodboard = ctaMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = ctaPrompts[fixture.id] || fixture.prompt;
    } else if (isTipsEduStoryActive) {
      dynMoodboard = tipsMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = tipsPrompts[fixture.id] || fixture.prompt;
    } else if (isCollecCatStoryActive) {
      dynMoodboard = collecMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = collecPrompts[fixture.id] || fixture.prompt;
    } else if (isDayNightStoryActive) {
      dynMoodboard = dayNightMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = dayNightPrompts[fixture.id] || fixture.prompt;
    } else if (isMoodboardStoryActive) {
      dynMoodboard = moodboardMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = moodboardPrompts[fixture.id] || fixture.prompt;
    } else if (isStyleThisStoryActive) {
      dynMoodboard = styleMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = stylePrompts[fixture.id] || fixture.prompt;
    } else if (isMythFactStoryActive) {
      dynMoodboard = mythFactMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = mythFactPrompts[fixture.id] || fixture.prompt;
    } else if (isOneProductThreeStylesFeedActive) {
      dynMoodboard = oneProductThreeStylesMoodboards[fixture.id] || fixture.moodboardId;
    } else if (isTipsEduFeedActive) {
      dynMoodboard = tipsEduFeedMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = tipsEduFeedPrompts[fixture.id] || fixture.prompt;
    } else if (isMoodboard1FeedActive) {
      dynMoodboard = mb1FeedMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = mb1FeedPrompts[fixture.id] || fixture.prompt;
    } else if (isMoodboard2FeedActive) {
      dynMoodboard = mb2FeedMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = mb2FeedPrompts[fixture.id] || fixture.prompt;
    } else if (isDayNightFeedActive) {
      dynMoodboard = dayNightFeedMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = dayNightFeedPrompts[fixture.id] || fixture.prompt;
    } else if (isProductCloseupReelActive) {
      dynMoodboard = productCloseupReelMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = productCloseupReelPrompts[fixture.id] || fixture.prompt;
    } else if (isDayNightReelActive) {
      dynMoodboard = dayNightReelMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = dayNightReelPrompts[fixture.id] || fixture.prompt;
    } else if (isBeforeAfterReelActive) {
      dynMoodboard = beforeAfterReelMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = beforeAfterReelPrompts[fixture.id] || fixture.prompt;
    } else if (isStyleReelActive) {
      dynMoodboard = styleReelMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = styleReelPrompts[fixture.id] || fixture.prompt;
    } else if (isMoodboardReelActive) {
      dynMoodboard = moodboardReelMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = moodboardReelPrompts[fixture.id] || fixture.prompt;
    } else if (isOneProductThreeStylesReelActive) {
      dynMoodboard = oneProductThreeStylesReelMoodboards[fixture.id] || fixture.moodboardId;
      dynPrompt = oneProductThreeStylesReelPrompts[fixture.id] || fixture.prompt;
    }

    setConfirmModalFixture({
      ...fixture,
      moodboardId: dynMoodboard,
      prompt: dynPrompt,
    });
  };

  // Handle direct edit of moodboard on a card
  const handleOpenEditMoodboard = (fixture: FixtureData) => {
    let currentMb = fixture.moodboardId || '';
    if (isCtaStoryActive) currentMb = ctaMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isTipsEduStoryActive) currentMb = tipsMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isCollecCatStoryActive) currentMb = collecMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isDayNightStoryActive) currentMb = dayNightMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isMoodboardStoryActive) currentMb = moodboardMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isStyleThisStoryActive) currentMb = styleMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isMythFactStoryActive) currentMb = mythFactMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isOneProductThreeStylesFeedActive) currentMb = oneProductThreeStylesMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isTipsEduFeedActive) currentMb = tipsEduFeedMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isMoodboard1FeedActive) currentMb = mb1FeedMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isMoodboard2FeedActive) currentMb = mb2FeedMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isDayNightFeedActive) currentMb = dayNightFeedMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isProductCloseupReelActive) currentMb = productCloseupReelMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isDayNightReelActive) currentMb = dayNightReelMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isBeforeAfterReelActive) currentMb = beforeAfterReelMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isStyleReelActive) currentMb = styleReelMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isMoodboardReelActive) currentMb = moodboardReelMoodboards[fixture.id] || fixture.moodboardId || '';
    else if (isOneProductThreeStylesReelActive) currentMb = oneProductThreeStylesReelMoodboards[fixture.id] || fixture.moodboardId || '';

    setEditMoodboardFixture(fixture);
    setEditMoodboardInput(currentMb);
  };

  const handleSaveMoodboard = async () => {
    if (!editMoodboardFixture) return;
    const newId = editMoodboardInput.trim();
    if (!newId) {
      toast.error('Moodboard ID cannot be empty');
      return;
    }
    setIsSavingMoodboard(true);
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';

    const endpoint = getActivePipelineConfig()?.runEndpoint.replace(/\/run$/, '/moodboard');
    if (!endpoint) {
      setIsSavingMoodboard(false);
      toast.error('No moodboard editor is available for this tab');
      return;
    }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({
          fixture_id: editMoodboardFixture.id,
          moodboard_id: newId,
          pin: pin,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        if (isCtaStoryActive) {
          setCtaMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isTipsEduStoryActive) {
          setTipsMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isCollecCatStoryActive) {
          setCollecMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isDayNightStoryActive) {
          setDayNightMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isMoodboardStoryActive) {
          setMoodboardMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isStyleThisStoryActive) {
          setStyleMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isMythFactStoryActive) {
          setMythFactMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isOneProductThreeStylesFeedActive) {
          setOneProductThreeStylesMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isTipsEduFeedActive) {
          setTipsEduFeedMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isMoodboard1FeedActive) {
          setMb1FeedMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isMoodboard2FeedActive) {
          setMb2FeedMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isDayNightFeedActive) {
          setDayNightFeedMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isProductCloseupReelActive) {
          setProductCloseupReelMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isDayNightReelActive) {
          setDayNightReelMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isBeforeAfterReelActive) {
          setBeforeAfterReelMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isStyleReelActive) {
          setStyleReelMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isMoodboardReelActive) {
          setMoodboardReelMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        } else if (isOneProductThreeStylesReelActive) {
          setOneProductThreeStylesReelMoodboards(prev => ({ ...prev, [editMoodboardFixture.id]: newId }));
        }
        toast.success(`Updated Moodboard ID for ${editMoodboardFixture.name} in .env`);
        setEditMoodboardFixture(null);
      } else {
        toast.error(data.error || 'Failed to update Moodboard ID');
      }
    } catch (err) {
      toast.error(`Error saving moodboard: ${err}`);
    } finally {
      setIsSavingMoodboard(false);
    }
  };

  // Handle direct edit of prompt on a card
  const handleOpenEditPrompt = (fixture: FixtureData) => {
    let currentPr = fixture.prompt || '';
    if (isCtaStoryActive) currentPr = ctaPrompts[fixture.id] || fixture.prompt || '';
    else if (isTipsEduStoryActive) currentPr = tipsPrompts[fixture.id] || fixture.prompt || '';
    else if (isCollecCatStoryActive) currentPr = collecPrompts[fixture.id] || fixture.prompt || '';
    else if (isDayNightStoryActive) currentPr = dayNightPrompts[fixture.id] || fixture.prompt || '';
    else if (isMoodboardStoryActive) currentPr = moodboardPrompts[fixture.id] || fixture.prompt || '';
    else if (isStyleThisStoryActive) currentPr = stylePrompts[fixture.id] || fixture.prompt || '';
    else if (isMythFactStoryActive) currentPr = mythFactPrompts[fixture.id] || fixture.prompt || '';
    else if (isTipsEduFeedActive) currentPr = tipsEduFeedPrompts[fixture.id] || fixture.prompt || '';
    else if (isMoodboard1FeedActive) currentPr = mb1FeedPrompts[fixture.id] || fixture.prompt || '';
    else if (isMoodboard2FeedActive) currentPr = mb2FeedPrompts[fixture.id] || fixture.prompt || '';
    else if (isOneProductThreeStylesFeedActive) currentPr = oneProductThreeStylesPrompts[fixture.id] || fixture.prompt || '';
    else if (isDayNightFeedActive) currentPr = dayNightFeedPrompts[fixture.id] || fixture.prompt || '';
    else if (isProductCloseupReelActive) currentPr = productCloseupReelPrompts[fixture.id] || fixture.prompt || '';
    else if (isDayNightReelActive) currentPr = dayNightReelPrompts[fixture.id] || fixture.prompt || '';
    else if (isBeforeAfterReelActive) currentPr = beforeAfterReelPrompts[fixture.id] || fixture.prompt || '';
    else if (isStyleReelActive) currentPr = styleReelPrompts[fixture.id] || fixture.prompt || '';
    else if (isMoodboardReelActive) currentPr = moodboardReelPrompts[fixture.id] || fixture.prompt || '';
    else if (isOneProductThreeStylesReelActive) currentPr = oneProductThreeStylesReelPrompts[fixture.id] || fixture.prompt || '';

    setEditPromptFixture(fixture);
    setEditPromptInput(currentPr);
  };

  const handleSavePrompt = async () => {
    if (!editPromptFixture) return;
    const newPr = editPromptInput.trim();
    if (!newPr) {
      toast.error('Prompt cannot be empty');
      return;
    }
    setIsSavingPrompt(true);
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';

    const endpoint = getActivePipelineConfig()?.runEndpoint.replace(/\/run$/, '/prompt');
    if (!endpoint) {
      setIsSavingPrompt(false);
      toast.error('No interior prompt editor is available for this tab');
      return;
    }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({
          fixture_id: editPromptFixture.id,
          prompt: newPr,
          pin: pin,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        if (isCtaStoryActive) {
          setCtaPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isTipsEduStoryActive) {
          setTipsPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isCollecCatStoryActive) {
          setCollecPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isDayNightStoryActive) {
          setDayNightPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isMoodboardStoryActive) {
          setMoodboardPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isStyleThisStoryActive) {
          setStylePrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isMythFactStoryActive) {
          setMythFactPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isTipsEduFeedActive) {
          setTipsEduFeedPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isMoodboard1FeedActive) {
          setMb1FeedPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isMoodboard2FeedActive) {
          setMb2FeedPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isOneProductThreeStylesFeedActive) {
          setOneProductThreeStylesPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isDayNightFeedActive) {
          setDayNightFeedPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isProductCloseupReelActive) {
          setProductCloseupReelPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isDayNightReelActive) {
          setDayNightReelPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isBeforeAfterReelActive) {
          setBeforeAfterReelPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isStyleReelActive) {
          setStyleReelPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isMoodboardReelActive) {
          setMoodboardReelPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        } else if (isOneProductThreeStylesReelActive) {
          setOneProductThreeStylesReelPrompts(prev => ({ ...prev, [editPromptFixture.id]: newPr }));
        }
        toast.success(`Updated Krea Prompt for ${editPromptFixture.name} in .env`);
        setEditPromptFixture(null);
      } else {
        toast.error(data.error || 'Failed to update Prompt');
      }
    } catch (err) {
      toast.error(`Error saving prompt: ${err}`);
    } finally {
      setIsSavingPrompt(false);
    }
  };

  // Handle confirmed run from modal
  const handleConfirmRun = async (customMoodboardId?: string, customPrompt?: string, maxItems: number = 1) => {
    if (!confirmModalFixture) return;
    const config = getActivePipelineConfig();
    if (!config) return;

    if (customMoodboardId) {
      if (config.type === 'cta') {
        setCtaMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'tips-edu') {
        setTipsMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'collec-story') {
        setCollecMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'day-night-story') {
        setDayNightMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'moodboard-story') {
        setMoodboardMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'style-this') {
        setStyleMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'myth-fact-story') {
        setMythFactMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'one-product-3-styles') {
        setOneProductThreeStylesMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'tips-edu-feed') {
        setTipsEduFeedMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'moodboard-1-feed') {
        setMb1FeedMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'moodboard-2-feed') {
        setMb2FeedMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'day-night-feed') {
        setDayNightFeedMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'product-closeup-reel') {
        setProductCloseupReelMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'day-night-reel') {
        setDayNightReelMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'before-after-reel') {
        setBeforeAfterReelMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'style-reel-slideshow') {
        setStyleReelMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'moodboard-reel') {
        setMoodboardReelMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      } else if (config.type === 'one-product-three-styles-reel') {
        setOneProductThreeStylesReelMoodboards(prev => ({ ...prev, [confirmModalFixture.id]: customMoodboardId }));
      }
    }

    if (customPrompt) {
      if (config.type === 'cta') {
        setCtaPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'tips-edu') {
        setTipsPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'collec-story') {
        setCollecPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'day-night-story') {
        setDayNightPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'moodboard-story') {
        setMoodboardPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'style-this') {
        setStylePrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'myth-fact-story') {
        setMythFactPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'tips-edu-feed') {
        setTipsEduFeedPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'moodboard-1-feed') {
        setMb1FeedPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'moodboard-2-feed') {
        setMb2FeedPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'one-product-3-styles') {
        setOneProductThreeStylesPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'day-night-feed') {
        setDayNightFeedPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'product-closeup-reel') {
        setProductCloseupReelPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'day-night-reel') {
        setDayNightReelPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'before-after-reel') {
        setBeforeAfterReelPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'style-reel-slideshow') {
        setStyleReelPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'moodboard-reel') {
        setMoodboardReelPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      } else if (config.type === 'one-product-three-styles-reel') {
        setOneProductThreeStylesReelPrompts(prev => ({ ...prev, [confirmModalFixture.id]: customPrompt }));
      }
    }

    setIsStartingRun(true);
    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch('/api/queue/enqueue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({
          pipeline_type: config.type,
          pipeline_name: config.name,
          fixture_id: confirmModalFixture.id,
          fixture_name: confirmModalFixture.name,
          format_tab: activeTab,
          subtab_index: activeSubTab,
          table_id: confirmModalFixture.tableId ?? '',
          moodboard_id: customMoodboardId,
          prompt: customPrompt,
          max_items: maxItems,
          run_endpoint: config.runEndpoint,
          status_endpoint: config.statusEndpoint,
          stop_endpoint: config.stopEndpoint,
          pin: pin,
        }),
      });

      let data: any = {};
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        data = await res.json();
      } else {
        const rawText = await res.text();
        throw new Error(`Server returned HTTP ${res.status}: ${rawText.slice(0, 100).replace(/<[^>]*>/g, '').trim()}`);
      }

      if (res.status === 401 || data.needs_pin) {
        setPinInput('');
        setShowPinModal(true);
        toast.error('Studio PIN required to trigger pipeline');
        return;
      }
      if (res.ok) {
        if (data.status === 'queued') {
          toast.success(`Added ${confirmModalFixture.name} to Generation Queue (#${data.queue_position} in line)`);
        } else {
          toast.info(`Started ${config.name} pipeline for ${confirmModalFixture.name} (${maxItems} item${maxItems > 1 ? 's' : ''})`);
          setRunningPipelineType(config.type);
          setPipelineState({
            status: 'running',
            active_fixture: confirmModalFixture.id,
            active_table_id: confirmModalFixture.tableId ?? null,
            current_phase: `Phase 1/${config.totalPhases}: Initializing Pipeline...`,
            current_phase_index: 1,
            total_phases: config.totalPhases,
            elapsed_seconds: 0,
            logs: [`[START] Triggered ${config.name} Pipeline for ${confirmModalFixture.name} (${confirmModalFixture.tableId})...`],
          });
        }
        setConfirmModalFixture(null);
      } else {
        toast.error(data.message || data.error || 'Failed to start pipeline');
      }
    } catch (err) {
      toast.error(`Network error: ${err}`);
    } finally {
      setIsStartingRun(false);
    }
  };

  // Handle stopping the running pipeline
  const handleStopPipeline = async () => {
    let stopEndpoint = '/api/cta/stop';
    if (runningPipelineType === 'tips-edu' || (!runningPipelineType && isTipsEduStoryActive)) {
      stopEndpoint = '/api/tips-edu/stop';
    } else if (runningPipelineType === 'collec-story' || (!runningPipelineType && isCollecCatStoryActive)) {
      stopEndpoint = '/api/collection-story/stop';
    } else if (runningPipelineType === 'day-night-story' || (!runningPipelineType && isDayNightStoryActive)) {
      stopEndpoint = '/api/day-night-story/stop';
    } else if (runningPipelineType === 'moodboard-story' || (!runningPipelineType && isMoodboardStoryActive)) {
      stopEndpoint = '/api/moodboard-story/stop';
    } else if (runningPipelineType === 'product-specs' || (!runningPipelineType && isProductSpecsStoryActive)) {
      stopEndpoint = '/api/product-specs/stop';
    } else if (runningPipelineType === 'style-this' || (!runningPipelineType && isStyleThisStoryActive)) {
      stopEndpoint = '/api/style-this/stop';
    } else if (runningPipelineType === 'myth-fact-story' || (!runningPipelineType && isMythFactStoryActive)) {
      stopEndpoint = '/api/myth-fact-story/stop';
    } else if (runningPipelineType === 'product-desc-story' || (!runningPipelineType && isProductDescStoryActive)) {
      stopEndpoint = '/api/product-description-story/stop';
    } else if (runningPipelineType === 'this-or-that-story' || (!runningPipelineType && isThisOrThatStoryActive)) {
      stopEndpoint = '/api/this-or-that/stop';
    } else if (runningPipelineType === 'one-product-3-styles' || (!runningPipelineType && isOneProductThreeStylesFeedActive)) {
      stopEndpoint = '/api/one-product-3-styles/stop';
    } else if (runningPipelineType === 'tips-edu-feed' || (!runningPipelineType && isTipsEduFeedActive)) {
      stopEndpoint = '/api/tips-edu-feed/stop';
    } else if (runningPipelineType === 'collection-feed' || (!runningPipelineType && isCollecCatFeedActive)) {
      stopEndpoint = '/api/collection-feed/stop';
    } else if (runningPipelineType === 'moodboard-1-feed' || (!runningPipelineType && isMoodboard1FeedActive)) {
      stopEndpoint = '/api/moodboard-1-feed/stop';
    } else if (runningPipelineType === 'moodboard-2-feed' || (!runningPipelineType && isMoodboard2FeedActive)) {
      stopEndpoint = '/api/moodboard-2-feed/stop';
    } else if (runningPipelineType === 'day-night-feed' || (!runningPipelineType && isDayNightFeedActive)) {
      stopEndpoint = '/api/day-night-feed/stop';
    } else if (runningPipelineType === 'product-showcase-feed' || (!runningPipelineType && isProductShowcaseFeedActive)) {
      stopEndpoint = '/api/product-showcase-feed/stop';
    } else if (runningPipelineType === 'product-closeup-reel' || (!runningPipelineType && isProductCloseupReelActive)) {
      stopEndpoint = '/api/product-closeup-reel/stop';
    } else if (runningPipelineType === 'day-night-reel' || (!runningPipelineType && isDayNightReelActive)) {
      stopEndpoint = '/api/day-night-reel/stop';
    } else if (runningPipelineType === 'before-after-reel' || (!runningPipelineType && isBeforeAfterReelActive)) {
      stopEndpoint = '/api/before-after-reel/stop';
    } else if (runningPipelineType === 'style-reel-slideshow' || (!runningPipelineType && isStyleReelActive)) {
      stopEndpoint = '/api/style-reel-slideshow/stop';
    } else if (runningPipelineType === 'moodboard-reel' || (!runningPipelineType && isMoodboardReelActive)) {
      stopEndpoint = '/api/moodboard-reel/stop';
    } else if (runningPipelineType === 'one-product-three-styles-reel' || (!runningPipelineType && isOneProductThreeStylesReelActive)) {
      stopEndpoint = '/api/one-product-3-styles-reel/stop';
    }

    const pin = studioPin || localStorage.getItem('hc_studio_pin') || '';
    try {
      const res = await fetch(stopEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(pin ? { 'Authorization': `Bearer ${pin}`, 'X-Dashboard-PIN': pin } : {}),
        },
        body: JSON.stringify({ pin }),
      });
      if (res.ok) {
        toast.warning('Pipeline execution stopped by user');
        setRunningPipelineType(null);
        setPipelineState(prev => ({
          ...prev,
          status: 'stopped',
          logs: [...prev.logs, '[USER] Pipeline stopped by user.'],
        }));
      } else if (res.status === 401) {
        setShowPinModal(true);
        toast.error('Invalid PIN to stop pipeline');
      }
    } catch (err) {
      toast.error('Failed to stop pipeline');
    }
  };

  // Choose the fixtures array based on current tab & subtab
  const baseFixtures = isCtaStoryActive
    ? CTA_STORY_FIXTURES
    : isTipsEduStoryActive
      ? TIPS_EDU_STORY_FIXTURES
      : isCollecCatStoryActive
        ? COLLECTION_CATEGORY_STORY_FIXTURES
        : isDayNightStoryActive
          ? DAY_NIGHT_STORY_FIXTURES
          : isMoodboardStoryActive
            ? MOODBOARD_STORY_FIXTURES
            : isProductSpecsStoryActive
              ? PRODUCT_SPECS_STORY_FIXTURES
              : isStyleThisStoryActive
                ? STYLE_THIS_STORY_FIXTURES
                : isMythFactStoryActive
                  ? MYTH_FACT_STORY_FIXTURES
                  : isProductDescStoryActive
                    ? PRODUCT_DESCRIPTION_STORY_FIXTURES
                    : isThisOrThatStoryActive
                      ? THIS_OR_THAT_STORY_FIXTURES
                      : isTipsEduFeedActive
                        ? TIPS_EDU_FEED_FIXTURES
                        : isCollecCatFeedActive
                          ? COLLECTION_CATEGORY_FEED_FIXTURES
                          : isMoodboard1FeedActive
                            ? MOODBOARD_1_FEED_FIXTURES
                            : isMoodboard2FeedActive
                              ? MOODBOARD_2_FEED_FIXTURES
                              : isOneProductThreeStylesFeedActive
                                ? ONE_PRODUCT_THREE_STYLES_FIXTURES
                                : isDayNightFeedActive
                                  ? DAY_NIGHT_FEED_FIXTURES
                                  : isProductShowcaseFeedActive
                                    ? PRODUCT_SHOWCASE_FEED_FIXTURES
                                    : isProductCloseupReelActive
                                      ? PRODUCT_CLOSEUP_REEL_FIXTURES
                                      : isDayNightReelActive
                                        ? DAY_NIGHT_REEL_FIXTURES
                                        : isBeforeAfterReelActive
                                          ? BEFORE_AFTER_REEL_FIXTURES
                                          : isStyleReelActive
                                            ? STYLE_REEL_SLIDESHOW_FIXTURES
                                            : isMoodboardReelActive
                                              ? MOODBOARD_REEL_FIXTURES
                                              : isOneProductThreeStylesReelActive
                                                ? ONE_PRODUCT_THREE_STYLES_REEL_FIXTURES
                                                : DEFAULT_FIXTURES;

  const currentFixtures: FixtureData[] = baseFixtures.map(base => {
    const key = `${activeTab}-${activeSubTab}-${base.id}`;
    let dynamicMoodboard = base.moodboardId;
    let dynamicPrompt: string | undefined = undefined;
    if (isCtaStoryActive) {
      dynamicMoodboard = ctaMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = ctaPrompts[base.id];
    } else if (isTipsEduStoryActive) {
      dynamicMoodboard = tipsMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = tipsPrompts[base.id];
    } else if (isCollecCatStoryActive) {
      dynamicMoodboard = collecMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = collecPrompts[base.id];
    } else if (isDayNightStoryActive) {
      dynamicMoodboard = dayNightMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = dayNightPrompts[base.id];
    } else if (isMoodboardStoryActive) {
      dynamicMoodboard = moodboardMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = moodboardPrompts[base.id];
    } else if (isStyleThisStoryActive) {
      dynamicMoodboard = styleMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = stylePrompts[base.id];
    } else if (isMythFactStoryActive) {
      dynamicMoodboard = mythFactMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = mythFactPrompts[base.id];
    } else if (isOneProductThreeStylesFeedActive) {
      dynamicMoodboard = oneProductThreeStylesMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = oneProductThreeStylesPrompts[base.id] || base.prompt;
    } else if (isTipsEduFeedActive) {
      dynamicMoodboard = tipsEduFeedMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = tipsEduFeedPrompts[base.id];
    } else if (isMoodboard1FeedActive) {
      dynamicMoodboard = mb1FeedMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = mb1FeedPrompts[base.id];
    } else if (isMoodboard2FeedActive) {
      dynamicMoodboard = mb2FeedMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = mb2FeedPrompts[base.id];
    } else if (isDayNightFeedActive) {
      dynamicMoodboard = dayNightFeedMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = dayNightFeedPrompts[base.id];
    } else if (isProductCloseupReelActive) {
      dynamicMoodboard = productCloseupReelMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = productCloseupReelPrompts[base.id] || base.prompt;
    } else if (isDayNightReelActive) {
      dynamicMoodboard = dayNightReelMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = dayNightReelPrompts[base.id] || base.prompt;
    } else if (isBeforeAfterReelActive) {
      dynamicMoodboard = beforeAfterReelMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = beforeAfterReelPrompts[base.id] || base.prompt;
    } else if (isStyleReelActive) {
      dynamicMoodboard = styleReelMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = styleReelPrompts[base.id] || base.prompt;
    } else if (isMoodboardReelActive) {
      dynamicMoodboard = moodboardReelMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = moodboardReelPrompts[base.id] || base.prompt;
    } else if (isOneProductThreeStylesReelActive) {
      dynamicMoodboard = oneProductThreeStylesReelMoodboards[base.id] || base.moodboardId;
      dynamicPrompt = oneProductThreeStylesReelPrompts[base.id] || base.prompt;
    }
    let dynamicTableId = base.tableId;
    if (isTipsEduStoryActive && tipsTableIds[base.id]) {
      dynamicTableId = tipsTableIds[base.id];
    }
    return {
      ...base,
      tableId: dynamicTableId,
      moodboardId: dynamicMoodboard,
      prompt: dynamicPrompt,
      completed: progressState[key] ?? null,
      statusCounts: isCtaStoryActive
        ? ctaStatusCounts[base.id]
        : isTipsEduStoryActive
        ? tipsStatusCounts[base.id]
        : isCollecCatStoryActive
        ? collecStatusCounts[base.id]
        : isDayNightStoryActive
        ? dayNightStatusCounts[base.id]
        : isMoodboardStoryActive
        ? moodboardStatusCounts[base.id]
        : isProductSpecsStoryActive
        ? productSpecsStatusCounts[base.id]
        : isStyleThisStoryActive
        ? styleThisStatusCounts[base.id]
        : isMythFactStoryActive
        ? mythFactStatusCounts[base.id]
        : isProductDescStoryActive
        ? productDescStatusCounts[base.id]
        : isThisOrThatStoryActive
        ? thisOrThatStatusCounts[base.id]
        : isTipsEduFeedActive
        ? tipsEduFeedStatusCounts[base.id]
        : isCollecCatFeedActive
        ? collecFeedStatusCounts[base.id]
        : isMoodboard1FeedActive
        ? mb1FeedStatusCounts[base.id]
        : isMoodboard2FeedActive
        ? mb2FeedStatusCounts[base.id]
        : isOneProductThreeStylesFeedActive
        ? oneProductThreeStylesStatusCounts[base.id]
        : isDayNightFeedActive
        ? dayNightFeedStatusCounts[base.id]
        : isProductShowcaseFeedActive
        ? prodShowcaseFeedStatusCounts[base.id]
        : isProductCloseupReelActive
        ? productCloseupReelStatusCounts[base.id]
        : isDayNightReelActive
        ? dayNightReelStatusCounts[base.id]
        : isBeforeAfterReelActive
        ? beforeAfterReelStatusCounts[base.id]
        : isStyleReelActive
        ? styleReelStatusCounts[base.id]
        : isMoodboardReelActive
        ? moodboardReelStatusCounts[base.id]
        : isOneProductThreeStylesReelActive
        ? oneProductThreeStylesReelStatusCounts[base.id]
        : undefined,
    };
  });

  // Computed live totals for the active subtab
  const activeSubtabHasCounts = currentFixtures.every(f => f.completed !== null);
  const activeSubtabCompleted = activeSubtabHasCounts
    ? currentFixtures.reduce((acc, f) => acc + (f.completed ?? 0), 0)
    : null;
  const activeSubtabTotal = currentFixtures.reduce((acc, f) => acc + (f.total ?? 100), 0);
  const activeSubtabPercentage = activeSubtabCompleted !== null && activeSubtabTotal > 0
    ? Math.round((activeSubtabCompleted / activeSubtabTotal) * 100)
    : null;

  // Aggregated 5-badge status rollup across all fixtures in active subtab
  const aggregatedStatusCounts = currentFixtures.reduce(
    (acc, f) => {
      if (f.statusCounts) {
        acc.P += f.statusCounts.P || 0;
        acc.S += f.statusCounts.S || 0;
        acc.C += f.statusCounts.C || 0;
        acc.D += f.statusCounts.D || 0;
        acc.FM += f.statusCounts.FM || 0;
        acc.hasCounts = true;
      }
      return acc;
    },
    { P: 0, S: 0, C: 0, D: 0, FM: 0, hasCounts: false }
  );

  // Compute live completed & total counts for any subtab from progressState
  const getSubtabTotals = (tab: TabType, subtabIdx: number) => {
    const fixtures = getFixturesForSubtab(tab, subtabIdx);
    const values = fixtures.map(f => progressState[`${tab}-${subtabIdx}-${f.id}`]);
    const completed = values.some(value => value === undefined)
      ? null
      : values.reduce((sum, value) => sum + value, 0);
    const total = fixtures.reduce((sum, f) => sum + (f.total ?? 100), 0);
    return { completed, total };
  };

  // Compute live completed & total counts for a format (Feed, Story, Reel)
  const getFormatTotals = (tab: TabType) => {
    const items = CONTENT_CONFIG[tab].items;
    let completed: number | null = 0;
    let total = 0;
    for (let i = 0; i < items.length; i++) {
      const sub = getSubtabTotals(tab, i);
      if (sub.completed === null) completed = null;
      else if (completed !== null) completed += sub.completed;
      total += sub.total;
    }
    return { completed, total };
  };

  const formatCounts = {
    feed: getFormatTotals('feed'),
    story: getFormatTotals('story'),
    reel: getFormatTotals('reel'),
  };
  const activeFormatSubtabCounts = activeFormat.items.map((_, index) =>
    getSubtabTotals(activeTab, index)
  );

  const getRunningTabInfo = (): { tab: TabType | null; subTab: number | null } => {
    if (!runningPipelineType || pipelineState.status !== 'running') return { tab: null, subTab: null };

    // Stories
    if (runningPipelineType === 'cta') return { tab: 'story', subTab: 0 };
    if (runningPipelineType === 'tips-edu') return { tab: 'story', subTab: 1 };
    if (runningPipelineType === 'collec-story') return { tab: 'story', subTab: 2 };
    if (runningPipelineType === 'day-night-story') return { tab: 'story', subTab: 3 };
    if (runningPipelineType === 'moodboard-story') return { tab: 'story', subTab: 4 };
    if (runningPipelineType === 'product-specs') return { tab: 'story', subTab: 5 };
    if (runningPipelineType === 'style-this') return { tab: 'story', subTab: 6 };
    if (runningPipelineType === 'myth-fact-story') return { tab: 'story', subTab: 7 };
    if (runningPipelineType === 'product-desc-story') return { tab: 'story', subTab: 8 };
    if (runningPipelineType === 'this-or-that-story') return { tab: 'story', subTab: 9 };
    
    // Feeds
    if (runningPipelineType === 'tips-edu-feed') return { tab: 'feed', subTab: 0 };
    if (runningPipelineType === 'collection-feed') return { tab: 'feed', subTab: 1 };
    if (runningPipelineType === 'moodboard-1-feed') return { tab: 'feed', subTab: 2 };
    if (runningPipelineType === 'moodboard-2-feed') return { tab: 'feed', subTab: 3 };
    if (runningPipelineType === 'one-product-3-styles') return { tab: 'feed', subTab: 4 };
    if (runningPipelineType === 'day-night-feed') return { tab: 'feed', subTab: 5 };
    if (runningPipelineType === 'product-showcase-feed') return { tab: 'feed', subTab: 6 };
    
    // Reels
    if (runningPipelineType === 'product-closeup-reel') return { tab: 'reel', subTab: 0 };
    if (runningPipelineType === 'day-night-reel') return { tab: 'reel', subTab: 1 };
    if (runningPipelineType === 'before-after-reel') return { tab: 'reel', subTab: 2 };
    if (runningPipelineType === 'style-reel-slideshow') return { tab: 'reel', subTab: 3 };
    if (runningPipelineType === 'moodboard-reel') return { tab: 'reel', subTab: 4 };
    if (runningPipelineType === 'one-product-three-styles-reel') return { tab: 'reel', subTab: 5 };

    return { tab: null, subTab: null };
  };

  const { tab: runningTab, subTab: runningSubTab } = getRunningTabInfo();
  const isCurrentTabPipelineRunning = runningTab === activeTab && runningSubTab === activeSubTab;

  const activePipelineConfig = getActivePipelineConfig();

  const isMoodboardEditable =
    isCtaStoryActive ||
    isTipsEduStoryActive ||
    isCollecCatStoryActive ||
    isDayNightStoryActive ||
    isMoodboardStoryActive ||
    isStyleThisStoryActive ||
    isMythFactStoryActive ||
    isTipsEduFeedActive ||
    isMoodboard1FeedActive ||
    isMoodboard2FeedActive ||
    isOneProductThreeStylesFeedActive ||
    isDayNightFeedActive ||
    isProductCloseupReelActive ||
    isDayNightReelActive ||
    isBeforeAfterReelActive ||
    isStyleReelActive ||
    isMoodboardReelActive ||
    isOneProductThreeStylesReelActive;

  const isPromptEditable =
    isCtaStoryActive ||
    isTipsEduStoryActive ||
    isCollecCatStoryActive ||
    isDayNightStoryActive ||
    isMoodboardStoryActive ||
    isStyleThisStoryActive ||
    isMythFactStoryActive ||
    isTipsEduFeedActive ||
    isMoodboard1FeedActive ||
    isMoodboard2FeedActive ||
    isOneProductThreeStylesFeedActive ||
    isDayNightFeedActive ||
    isProductCloseupReelActive ||
    isDayNightReelActive ||
    isBeforeAfterReelActive ||
    isStyleReelActive ||
    isMoodboardReelActive ||
    isOneProductThreeStylesReelActive;

  const getPipelineFixtures = (pipelineType: string | null): Omit<FixtureData, 'completed'>[] => {
    if (!pipelineType) return DEFAULT_FIXTURES;
    switch (pipelineType) {
      case 'cta': return CTA_STORY_FIXTURES;
      case 'tips-edu': return TIPS_EDU_STORY_FIXTURES;
      case 'collec-story': return COLLECTION_CATEGORY_STORY_FIXTURES;
      case 'day-night-story': return DAY_NIGHT_STORY_FIXTURES;
      case 'moodboard-story': return MOODBOARD_STORY_FIXTURES;
      case 'product-specs': return PRODUCT_SPECS_STORY_FIXTURES;
      case 'style-this': return STYLE_THIS_STORY_FIXTURES;
      case 'myth-fact-story': return MYTH_FACT_STORY_FIXTURES;
      case 'product-desc-story': return PRODUCT_DESCRIPTION_STORY_FIXTURES;
      case 'this-or-that-story': return THIS_OR_THAT_STORY_FIXTURES;
      case 'tips-edu-feed': return TIPS_EDU_FEED_FIXTURES;
      case 'collection-feed': return COLLECTION_CATEGORY_FEED_FIXTURES;
      case 'moodboard-1-feed': return MOODBOARD_1_FEED_FIXTURES;
      case 'moodboard-2-feed': return MOODBOARD_2_FEED_FIXTURES;
      case 'one-product-3-styles': return ONE_PRODUCT_THREE_STYLES_FIXTURES;
      case 'day-night-feed': return DAY_NIGHT_FEED_FIXTURES;
      case 'product-showcase-feed': return PRODUCT_SHOWCASE_FEED_FIXTURES;
      case 'product-closeup-reel': return PRODUCT_CLOSEUP_REEL_FIXTURES;
      case 'day-night-reel': return DAY_NIGHT_REEL_FIXTURES;
      case 'before-after-reel': return BEFORE_AFTER_REEL_FIXTURES;
      case 'style-reel-slideshow': return STYLE_REEL_SLIDESHOW_FIXTURES;
      case 'moodboard-reel': return MOODBOARD_REEL_FIXTURES;
      case 'one-product-three-styles-reel': return ONE_PRODUCT_THREE_STYLES_REEL_FIXTURES;
      default: return DEFAULT_FIXTURES;
    }
  };

  const getPipelineLabel = (pipelineType: string | null): { format: string; subTab: string } => {
    if (!pipelineType) return { format: '', subTab: '' };
    switch (pipelineType) {
      case 'cta': return { format: 'Story', subTab: 'CTA' };
      case 'tips-edu': return { format: 'Story', subTab: 'Tips & Educational' };
      case 'collec-story': return { format: 'Story', subTab: 'Collection Category' };
      case 'day-night-story': return { format: 'Story', subTab: 'Day & Night' };
      case 'moodboard-story': return { format: 'Story', subTab: 'Moodboard Story' };
      case 'product-specs': return { format: 'Story', subTab: 'Product Specs' };
      case 'style-this': return { format: 'Story', subTab: 'Style This?' };
      case 'myth-fact-story': return { format: 'Story', subTab: 'Myth & Fact' };
      case 'product-desc-story': return { format: 'Story', subTab: 'Product Description' };
      case 'this-or-that-story': return { format: 'Story', subTab: 'This or That' };
      case 'tips-edu-feed': return { format: 'Feed', subTab: 'Tips & Educational' };
      case 'collection-feed': return { format: 'Feed', subTab: 'Collection Category' };
      case 'moodboard-1-feed': return { format: 'Feed', subTab: 'Moodboard #1' };
      case 'moodboard-2-feed': return { format: 'Feed', subTab: 'Moodboard #2' };
      case 'one-product-3-styles': return { format: 'Feed', subTab: '1 Product, 3 Styles' };
      case 'day-night-feed': return { format: 'Feed', subTab: 'Day & Night' };
      case 'product-showcase-feed': return { format: 'Feed', subTab: 'Product Showcase' };
      case 'product-closeup-reel': return { format: 'Reel', subTab: 'Product Closeup' };
      case 'day-night-reel': return { format: 'Reel', subTab: 'Day & Night' };
      case 'before-after-reel': return { format: 'Reel', subTab: 'Before & After' };
      case 'style-reel-slideshow': return { format: 'Reel', subTab: 'Style Reel Slideshow' };
      case 'moodboard-reel': return { format: 'Reel', subTab: 'Moodboard' };
      case 'one-product-three-styles-reel': return { format: 'Reel', subTab: '1 Product, 3 Styles' };
      default: return { format: '', subTab: '' };
    }
  };

  const runningPipelineInfo = getPipelineLabel(runningPipelineType);
  const runningFixturesList = getPipelineFixtures(runningPipelineType);
  const trueRunningFixtureObj = runningFixturesList.find(
    f => f.id === pipelineState.active_fixture
  );
  const runningFixtureDisplayName = trueRunningFixtureObj?.name || pipelineState.active_fixture || 'Fixture';

  const activeRunningFixtureId =
    isCurrentTabPipelineRunning && pipelineState.status === 'running'
      ? pipelineState.active_fixture
      : null;

  const activeRunningFixtureObj = trueRunningFixtureObj || currentFixtures.find(
    f => f.id === pipelineState.active_fixture
  );

  
  const getSubTabHeaderTitle = () => {
    if (isCtaStoryActive) return 'CTA Story Fixtures & Airtable Progress';
    if (isTipsEduStoryActive) return 'Tips & Educational Story Fixtures & Airtable Progress';
    if (isCollecCatStoryActive) return 'Collection Category Story Fixtures & Airtable Progress';
    if (isDayNightStoryActive) return 'Day & Night Story Fixtures & Airtable Progress';
    if (isMoodboardStoryActive) return 'Moodboard Story Fixtures & Airtable Progress';
    if (isProductSpecsStoryActive) return 'Product Closeup w/ Specs Fixtures & Airtable Progress';
    if (isStyleThisStoryActive) return 'Style This? Story Fixtures & Airtable Progress';
    if (isMythFactStoryActive) return 'Myth & Fact Story Fixtures & Airtable Progress';
    if (isProductDescStoryActive) return 'Product Closeup w/ Description Fixtures & Airtable Progress';
    if (isThisOrThatStoryActive) return 'This or That Story Fixtures & Airtable Progress';
    if (isTipsEduFeedActive) return 'Tips & Educational Feed Fixtures & Airtable Progress';
    if (isCollecCatFeedActive) return 'Collection Category Feed Fixtures & Airtable Progress';
    if (isMoodboard1FeedActive) return 'Moodboard #1 Feed Fixtures & Airtable Progress';
    if (isMoodboard2FeedActive) return 'Moodboard #2 Feed Fixtures & Airtable Progress';
    if (isOneProductThreeStylesFeedActive) return '1 Product, 3 Styles Feed Fixtures & Airtable Progress';
    if (isDayNightFeedActive) return 'Day & Night Feed Fixtures & Airtable Progress';
    if (isProductShowcaseFeedActive) return 'Product Showcase Feed Fixtures & Airtable Progress';
    if (isProductCloseupReelActive) return 'Product Closeup Reel Fixtures & Airtable Progress';
    if (isDayNightReelActive) return 'Day & Night Reel Fixtures & Airtable Progress';
    if (isBeforeAfterReelActive) return 'Before & After Reel Fixtures & Airtable Progress';
    if (isStyleReelActive) return 'Style Reel Slideshow Fixtures & Airtable Progress';
    if (isMoodboardReelActive) return 'Moodboard Reel Fixtures & Airtable Progress';
    if (isOneProductThreeStylesReelActive) return '1 Product, 3 Styles Reel Fixtures & Airtable Progress';
    return 'Lighting Fixtures Progress';
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 selection:bg-sky-100">
      <Toaster position="top-right" richColors />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Top Format Tabs (Feed, Story, Reel) */}
        <FormatTabs
          activeTab={activeTab}
          counts={formatCounts}
          onSelectTab={tab => {
            setActiveTab(tab);
            setActiveSubTab(0);
          }}
          runningTab={runningTab}
        />

        {/* Minimalist Sub-Tab Rail for Content Items */}
        <SubTabRail
          activeTab={activeTab}
          items={activeFormat.items}
          activeSubTab={activeSubTab}
          onSelectSubTab={idx => setActiveSubTab(idx)}
          runningSubTab={activeTab === runningTab ? runningSubTab : null}
          counts={activeFormatSubtabCounts}
        />

        {/* Section Header with Subtle Inline Refresh */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-6 mb-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-sm font-semibold text-gray-800">
              {getSubTabHeaderTitle()}
            </h2>

            {/* Subtab Live Completed Progress Badge Pill */}
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs"
              title={activeSubtabCompleted === null ? 'Airtable completed counts are loading' : `${activeSubtabCompleted} completed records out of ${activeSubtabTotal} target capacity across all ${currentFixtures.length} fixtures in this subtab`}
            >
              <Check className="w-3 h-3 text-emerald-600" />
              <span>{activeSubtabCompleted === null ? '— Completed' : `${activeSubtabCompleted} / ${activeSubtabTotal} Completed`}</span>
              {activeSubtabPercentage !== null && <span className="text-emerald-600/70 font-normal">({activeSubtabPercentage}%)</span>}
            </span>

            {/* Aggregated 5-Badge Status Rollup (P, S, C, D, FM) */}
            {aggregatedStatusCounts.hasCounts && (
              <div className="flex items-center gap-1">
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200/80 shadow-2xs"
                  title={`Total Posted: ${aggregatedStatusCounts.P} records across all fixtures in ${CONTENT_CONFIG[activeTab].items[activeSubTab]}`}
                >
                  <span className="font-bold text-sky-800">P:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.P}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200/80 shadow-2xs"
                  title={`Total Scheduled: ${aggregatedStatusCounts.S} records across all fixtures in ${CONTENT_CONFIG[activeTab].items[activeSubTab]}`}
                >
                  <span className="font-bold text-purple-800">S:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.S}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs"
                  title={`Total Completed (not posted): ${aggregatedStatusCounts.C} records across all fixtures in ${CONTENT_CONFIG[activeTab].items[activeSubTab]}`}
                >
                  <span className="font-bold text-emerald-800">C:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.C}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200/80 shadow-2xs"
                  title={`Total Discarded: ${aggregatedStatusCounts.D} records across all fixtures in ${CONTENT_CONFIG[activeTab].items[activeSubTab]}`}
                >
                  <span className="font-bold text-rose-800">D:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.D}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200/80 shadow-2xs"
                  title={`Total For Manual / Revisions: ${aggregatedStatusCounts.FM} records across all fixtures in ${CONTENT_CONFIG[activeTab].items[activeSubTab]}`}
                >
                  <span className="font-bold text-amber-800">FM:</span>
                  <span className="font-semibold tabular-nums">{aggregatedStatusCounts.FM}</span>
                </span>
              </div>
            )}
            {isInteractivePipelineActive && (
              <>
                <button
                  type="button"
                  onClick={() => fetchLiveCounts(true)}
                  disabled={isLoadingCounts || pipelineState.status === 'running'}
                  className="p-1 text-gray-400 hover:text-sky-600 hover:bg-sky-50 rounded-md transition-all disabled:opacity-40"
                  title="Auto-synced with Airtable. Click to refresh manually."
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingCounts ? 'animate-spin text-sky-600' : ''}`} />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPinInput(studioPin);
                    setShowPinModal(true);
                  }}
                  className={`p-1 rounded-md transition-all ${studioPin ? 'text-emerald-600 bg-emerald-50 hover:bg-emerald-100' : 'text-gray-400 hover:text-sky-600 hover:bg-sky-50'
                    }`}
                  title={studioPin ? 'Studio PIN Configured (Click to change)' : 'Configure Studio PIN'}
                >
                  <Key className="w-3.5 h-3.5" />
                </button>
                {tunnelInfo.active && (
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(tunnelInfo.public_url);
                      toast.success('Cloudflare public link copied to clipboard!');
                    }}
                    className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-300/80 rounded-full transition-all cursor-pointer shadow-xs"
                    title={`Cloudflare Live: ${tunnelInfo.public_url} (Click to copy)`}
                  >
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                    </span>
                    <Globe className="w-3 h-3 text-amber-600" />
                    <span className="hidden sm:inline">Public Live</span>
                  </button>
                )}
              </>
            )}
          </div>
          {isInteractivePipelineActive && (
            <span className="text-[11px] text-gray-400 font-medium hidden sm:inline">
              Auto-synced on completion
            </span>
          )}
        </div>

        {/* Global Persistent Background Processing Banner when viewing another tab */}
        {pipelineState.status === 'running' && !isCurrentTabPipelineRunning && (
          <div className="mb-6 p-4 bg-gradient-to-r from-sky-950 via-slate-900 to-indigo-950 text-white rounded-2xl shadow-xl border border-sky-600/40 flex flex-wrap items-center justify-between gap-4 animate-in slide-in-from-top-2 duration-200">
            <div className="flex items-center gap-3.5">
              <div className="relative flex h-3.5 w-3.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-sky-500"></span>
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 bg-sky-500/20 text-sky-300 border border-sky-400/30 rounded-full text-[10px] font-bold tracking-wider uppercase">
                    Background Processing
                  </span>
                  <span className="font-semibold text-sm text-white">
                    {runningPipelineInfo.format} › {runningPipelineInfo.subTab}
                  </span>
                  <span className="text-xs text-sky-200 font-medium px-2 py-0.5 bg-sky-900/50 rounded-md border border-sky-700/40">
                    {runningFixtureDisplayName}
                  </span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300 mt-1.5">
                  <span className="font-medium text-slate-200">{pipelineState.current_phase || 'Processing...'}</span>
                  <span>•</span>
                  <span className="font-mono text-sky-300">
                    {Math.floor(pipelineState.elapsed_seconds / 60).toString().padStart(2, '0')}:{(pipelineState.elapsed_seconds % 60).toString().padStart(2, '0')}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (runningTab && runningSubTab !== null) {
                    setActiveTab(runningTab);
                    setActiveSubTab(runningSubTab);
                  }
                }}
                className="px-3.5 py-1.5 bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-bold rounded-xl shadow-md transition-all flex items-center gap-1.5 cursor-pointer"
              >
                <span>Jump to {runningPipelineInfo.subTab} Tab</span>
                <span>→</span>
              </button>
              <button
                type="button"
                onClick={handleStopPipeline}
                className="px-3 py-1.5 bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-medium rounded-xl transition-all cursor-pointer"
              >
                Stop
              </button>
            </div>
          </div>
        )}

        {/* Global Pipeline Execution Console & Monitor */}
        {(pipelineState.status === 'running' || pipelineState.status === 'error') && (
          <div className="mb-6 animate-in fade-in duration-150 relative">
            <LiveLogViewer
              pipelineState={pipelineState}
              onStop={handleStopPipeline}
              onClearLogs={() => setPipelineState(prev => ({ ...prev, logs: [] }))}
              fixtureName={
                !isCurrentTabPipelineRunning
                  ? `${runningPipelineInfo.format} › ${runningPipelineInfo.subTab} › ${runningFixtureDisplayName}`
                  : `${runningPipelineInfo.subTab || activeFormat.items[activeSubTab]} › ${runningFixtureDisplayName}`
              }
            />
          </div>
        )}

        {/* Pipeline Error Alert Banner */}
        {pipelineState.status === 'error' && pipelineState.error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center justify-between text-xs text-rose-900 shadow-xs animate-in fade-in duration-150">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0"></span>
              <div>
                <span className="font-semibold">Pipeline Error: </span>
                <span className="text-rose-800">{pipelineState.error}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setPipelineState(prev => ({ ...prev, status: 'idle', error: undefined }))}
              className="px-2.5 py-1 bg-rose-200/60 hover:bg-rose-200 text-rose-900 rounded-lg font-medium transition-all text-[11px] cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Lighting Fixtures Progress Grid */}
        <FixtureProgressGrid
          fixtures={currentFixtures}
          activeTab={activeTab}
          activeRunningFixtureId={
            activeQueueJob && activeQueueJob.pipeline_type === activePipelineConfig?.type
              ? activeQueueJob.fixture_id
              : activeRunningFixtureId
          }
          currentPhase={
            activeQueueJob && activeQueueJob.pipeline_type === activePipelineConfig?.type
              ? activeQueueJob.current_phase
              : (isCurrentTabPipelineRunning ? pipelineState.current_phase : undefined)
          }
          onRunFixture={isInteractivePipelineActive ? handleOpenRunModal : undefined}
          onStopFixture={handleStopActiveJob}
          onCancelQueueFixture={handleCancelQueueFixture}
          getQueueInfo={getQueueInfo}
          isAnyPipelineRunning={!!activeQueueJob || pipelineState.status === 'running'}
          canRun={true}
          onEditMoodboard={isMoodboardEditable ? handleOpenEditMoodboard : undefined}
          onEditPrompt={isPromptEditable ? handleOpenEditPrompt : undefined}
          onViewRows={handleOpenRowInspector}
          hideProgressBar={isCtaStoryActive || isTipsEduStoryActive || isOneProductThreeStylesFeedActive}
        />
      </div>

      {/* Confirmation Modal */}
      <RunConfirmModal
        fixture={confirmModalFixture}
        pipelineTitle={activePipelineConfig ? `Run ${activePipelineConfig.name} Pipeline` : 'Run Story Pipeline'}
        totalPhases={activePipelineConfig?.totalPhases ?? 5}
        phaseSummary={activePipelineConfig?.phaseSummary}
        onConfirm={handleConfirmRun}
        onClose={() => setConfirmModalFixture(null)}
        isLoading={isStartingRun}
      />

      {/* Airtable Row Inspector Modal */}
      <RowInspectorModal
        fixture={inspectFixture}
        initialStatusFilter={inspectStatusFilter}
        onClose={() => setInspectFixture(null)}
      />

      {/* Direct Edit Moodboard Modal */}
      {editMoodboardFixture && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-md w-full p-6 text-gray-900 relative">
            <button
              onClick={() => setEditMoodboardFixture(null)}
              disabled={isSavingMoodboard}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="mb-4 pr-6">
              <h3 className="text-lg font-bold text-gray-900">Change Krea Moodboard ID</h3>
              <p className="text-xs text-gray-500">{editMoodboardFixture.name} ({activePipelineConfig?.name || 'Story'})</p>
            </div>

            <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 mb-5 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 font-medium">Fixture:</span>
                <span className="font-semibold text-gray-900">{editMoodboardFixture.name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 font-medium">Airtable Table ID:</span>
                <span className="font-mono text-xs bg-gray-200 px-2 py-0.5 rounded text-gray-800">
                  {editMoodboardFixture.tableId}
                </span>
              </div>
              <div className="space-y-1 pt-1">
                <label className="text-xs font-semibold text-gray-700 block">
                  Krea Moodboard UUID:
                </label>
                <input
                  type="text"
                  value={editMoodboardInput}
                  onChange={(e) => setEditMoodboardInput(e.target.value.trim())}
                  placeholder="e.g. 0844ad92-c34a-4dc8-9d70-d09498dc098c"
                  className="w-full font-mono text-xs bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setEditMoodboardFixture(null)}
                disabled={isSavingMoodboard}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveMoodboard}
                disabled={isSavingMoodboard || !editMoodboardInput.trim()}
                className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-lg shadow-xs hover:shadow transition-all disabled:opacity-50"
              >
                {isSavingMoodboard ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>Save Moodboard ID</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Direct Edit Prompt Modal */}
      {editPromptFixture && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-lg w-full p-6 text-gray-900 relative">
            <button
              onClick={() => setEditPromptFixture(null)}
              disabled={isSavingPrompt}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="mb-4 pr-6">
              <h3 className="text-lg font-bold text-gray-900">Edit Krea Interior Generation Prompt</h3>
              <p className="text-xs text-gray-500">{editPromptFixture.name} ({activePipelineConfig?.name || 'Story'})</p>
            </div>

            <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 mb-5 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 font-medium">Fixture:</span>
                <span className="font-semibold text-gray-900">{editPromptFixture.name}</span>
              </div>
              <div className="space-y-1 pt-1">
                <label className="text-xs font-semibold text-gray-700 block">
                  Krea Interior Prompt:
                </label>
                <textarea
                  rows={3}
                  value={editPromptInput}
                  onChange={(e) => setEditPromptInput(e.target.value)}
                  placeholder="e.g. Generate me a modern living room"
                  className="w-full text-xs bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-amber-500 focus:border-amber-500 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setEditPromptFixture(null)}
                disabled={isSavingPrompt}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSavePrompt}
                disabled={isSavingPrompt || !editPromptInput.trim()}
                className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 active:bg-amber-800 rounded-lg shadow-xs hover:shadow transition-all disabled:opacity-50"
              >
                {isSavingPrompt ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>Save Prompt</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Studio Security PIN Modal */}
      {showPinModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5 border border-gray-100 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
                  <Key className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900">Studio Security PIN</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowPinModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-4">
              Enter your Studio PIN to authorize paid AI generation pipelines and protect API credits.
            </p>
            <input
              type="password"
              value={pinInput}
              onChange={e => setPinInput(e.target.value)}
              placeholder="Enter PIN (e.g. 1234)"
              autoFocus
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 mb-4 font-mono"
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  const val = pinInput.trim();
                  localStorage.setItem('hc_studio_pin', val);
                  setStudioPin(val);
                  setShowPinModal(false);
                  toast.success('Studio PIN saved!');
                }
              }}
            />
            <div className="flex justify-end gap-2">
              {studioPin && (
                <button
                  type="button"
                  onClick={() => {
                    localStorage.removeItem('hc_studio_pin');
                    setStudioPin('');
                    setPinInput('');
                    setShowPinModal(false);
                    toast.info('Studio PIN cleared');
                  }}
                  className="px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-lg transition-all"
                >
                  Clear PIN
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowPinModal(false)}
                className="px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 rounded-lg transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const val = pinInput.trim();
                  localStorage.setItem('hc_studio_pin', val);
                  setStudioPin(val);
                  setShowPinModal(false);
                  toast.success('Studio PIN saved!');
                }}
                className="px-3.5 py-1.5 text-xs bg-sky-600 text-white font-medium rounded-lg hover:bg-sky-700 transition-all shadow-xs"
              >
                Save PIN
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Generation Queue Dock */}
      <QueueDock
        activeJob={activeQueueJob}
        queue={pendingQueue}
        history={queueHistory}
        onCancelQueueItem={handleCancelQueueItem}
        onClearQueue={handleClearQueue}
        onStopActiveJob={handleStopActiveJob}
      />
    </div>
  );
}

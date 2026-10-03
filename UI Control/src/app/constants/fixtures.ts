import { TabType, FixtureData } from '../types';

export const CONTENT_CONFIG: Record<TabType, { name: string; ratio: string; items: string[] }> = {
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
      'One at a time Lights',
      'Sketch to Real',
      'Room Build-Up',
    ],
  },
  adcover: {
    name: 'Ad Covers',
    ratio: '1:1 (1080 × 1080 px)',
    items: ['Ad Cover Chandelier'],
  },
  banner: {
    name: 'Banner Set',
    ratio: '21:9 + 1800 × 600 + 1800 × 600',
    items: ['Banner Set'],
  },
};

// The 5 CTA Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const CTA_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblYHdVq14FjMWg5o', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblfl7fqFZa2vUieB', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblSpGJLO3faYfIDY', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait' },
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblKJeCCp4zQ6g7Em', moodboardId: '351d992d-19e3-4b1e-aa46-08a842796c61', prompt: 'Generate me a modern bedroom with a table lamp side by side' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblPKSYyjgbgMypE2', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Modern living room interior, stylish lounge chair, warm ambient lighting, spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait' },
];

// The 6 Tips & Educational Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const TIPS_EDU_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblwnFN5a8fLzKuP4', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblJxWwZexgBHl26B', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate a premium modern interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp beside an armchair.' },
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblpFiaNn1Ym9fTTk', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room' },
  { id: 'ceiling-mounted', name: 'Ceiling Mounted', total: 100, tableId: 'tblGlRibUZXB9R3Gt', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate a premium modern hallway interior in a vertical 9:16 composition with clean walls and a plain flat ceiling.' },
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblZtENqILDAekLv2', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate a premium modern bedroom interior with a prominent bedside nightstand table surface.' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tbllzkE2prSyj9BaD', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate a premium modern high-ceiling living room interior with a spacious vertical ceiling volume.' },
];

// The 5 Collection Category Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const COLLECTION_CATEGORY_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblSSVJnubFk2yBm3', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room hanging pendant light not too oversize item' },
  { id: 'wall-light', name: 'Wall Lights', total: 100, tableId: 'tbl98UU0h4uFyFIlL', moodboardId: 'afa1317e-7be1-47f5-9d6f-91c7769a767d', prompt: 'Generate me a modern living room with wall sconce mounted on the wall' },
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblJMJQlrnlDb1GtN', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room hanging chandelier' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblloZLRSKwOCg247', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern bedroom that have beside a floor lamp' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblsXXcoZZD4q6WWt', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room with cluster chandelier hanging from the ceiling' },
];

// The 5 Day & Night Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const DAY_NIGHT_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblKkCf88UVQ3Yu07', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblaNyYZCR7E6TXtv', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room with plain ceiling for hanging pendant light' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblr1hlsjGcs9QKCy', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tblhvM9Saq18YqONB', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate me a modern bedroom with a bedside table for a table lamp' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblgcvB4WFKOpSIQl', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling for a cluster chandelier' },
];

// The 3 Moodboard Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const MOODBOARD_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblHQrci8d1K9ws2M', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblkm119i48y0M1IQ', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblBaNeiSZeYrUawW', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
];

// The Product Closeup w/ Specs fixtures (Chandelier + dynamic .env hooks)
export const PRODUCT_SPECS_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblEGTB6BodRVDqBV' },
];

// The 2 Style This? Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const STYLE_THIS_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblYge5R7LwTJkEHC', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblvSAzXasTVI85r9', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room' },
];

// The 3 Myth & Fact Story fixtures with actual Airtable Table IDs & Default Krea Moodboard IDs
export const MYTH_FACT_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbl3OI7crWvN2Q7u6', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblf5Yaki4ktwiLtx', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblwBnWYRGcV6as45', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
];

// The 6 Product Closeup w/ Description Story fixtures with actual Airtable Table IDs
export const PRODUCT_DESCRIPTION_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblDcT6jovdAbKnfw' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblDD2w4v0Idb4jAZ' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblPvHyKGByWJCMtY' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblnIOQVywHcTgAtv' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tbl5S9JEHSrjrLwxA' },
  { id: 'wall-light', name: 'Wall Light', total: 100, tableId: 'tblYqudlgjYMNRROM' },
];

// The 6 This or That Story fixtures with actual Airtable Table IDs
export const THIS_OR_THAT_STORY_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblo42IkuhYLIQBzk' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblS1VHp41RDfxztD' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblaoqj8VPVHFmVQn' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblYAhjKckXtjUayx' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tblm1Ty2QkAlUcHJt' },
  { id: 'wall-light', name: 'Wall Light', total: 100, tableId: 'tblZw6jvSa27oZDiN' },
];

// Subtab 0: Tips & Educational Feed (4:5)
export const TIPS_EDU_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblQ65S51Dmauwx4c', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room hanging chandelier from the ceiling' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblIhCP3Gjg09QFCK', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblQuhvktqYB59Ofw', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tblwY6eGQCD5bJeF1', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling for a cluster chandelier' },
];

// Subtab 1: Collection Category Feed (4:5)
export const COLLECTION_CATEGORY_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'collection', name: '5-Room Collection', total: 100, tableId: 'tbl5o1j3XvUaUqmjs' },
];

// Subtab 2: Moodboard #1 Feed (4:5)
export const MOODBOARD_1_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbl9u5vjgx8kuE44R', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblOvvYdgsNTXh2zK', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tbl6uTmwM23KK9ocO', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
];

// Subtab 3: Moodboard #2 Feed (4:5)
export const MOODBOARD_2_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbltWgQKOYjuHw6tx', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tbl4TiV90SzdBz4KG', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tbl4YF9iXlBqGblEc', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'wall-light', name: 'Wall Lights', total: 100, tableId: 'tbljUk9JwzS1JeZJg', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room with a wall light' },
];

// Subtab 4: The 3 1 Product, 3 Styles Feed fixtures (4:5)
export const ONE_PRODUCT_THREE_STYLES_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblRy52kCasisCWzd', moodboardId: '2a4a62bf-c6eb-49f8-8808-2543200634a0', prompt: 'Generate me a luxury modern dining room with hanging pendant light' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tbl9GIq2QeYCwMhWU', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a luxury modern living room lounge with standing floor lamp' },
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblrlfqBGe5EjS5PI', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a luxury modern grand living room with hanging chandelier' },
];

// Subtab 5: Day & Night Feed (4:5)
export const DAY_NIGHT_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblSceuLVvLMQ6wWp', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tblIgRlTtO7Y2EGIo', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room with plain ceiling for hanging pendant light' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblcKHAVYgzIcmabT', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tbljsKOEhc0618qbM', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate me a modern bedroom with a bedside table for a table lamp' },
];

// Subtab 6: Product Showcase Feed (4:5)
export const PRODUCT_SHOWCASE_FEED_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tbln0MNBaVVrZ0wrF' },
];

// Reel Subtab 0: Product Closeup Reel (9:16)
export const PRODUCT_CLOSEUP_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblqBZ946hVdOpmDV', moodboardId: 'fb2487fb-2895-4d2c-9758-805aaf1bac69', prompt: 'Generate me a modern bedroom nightstand' },
];

// Reel Subtab 1: Day & Night Reel (9:16)
export const DAY_NIGHT_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblkTuM627s2f0FTN', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'chandelier', name: 'Chandeliers', total: 100, tableId: 'tbl35JySlNuWh61tL', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern living room' },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100, tableId: 'tblVPgI4C6HEFcKW9', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
];

// Reel Subtab 2: Before & After Reel (9:16)
export const BEFORE_AFTER_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tbleUP86Kw36G8Hdw', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a modern dining room' },
  { id: 'chandelier', name: 'Chandeliers', total: 100, tableId: 'tbloMhCOngGDWFS2y', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a photo a modern living room hanging chandelier from the ceiling' },
];

// Reel Subtab 3: Style Reel Slideshow (9:16)
export const STYLE_REEL_SLIDESHOW_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'style-tour', name: '5-Room Style Tour', total: 100, tableId: 'tblFFEvkHb3jLKrcv', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate 5 coherent modern rooms for a cohesive home tour' },
];

// Reel Subtab 4: Moodboard Reel (9:16)
export const MOODBOARD_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier Modern', total: 100, tableId: 'tbl026zbECJJ9FRfj', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblpjRudEy6fobIrP', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern dining room' },
  { id: 'cluster-chandelier', name: 'Cluster Chandeliers', total: 100, tableId: 'tblJX6rd5nhhEuWbL', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling for cluster chandelier' },
  { id: 'linear-chandelier', name: 'Linear Chandeliers', total: 100, tableId: 'tblj4DVzllYa8pliK', moodboardId: '994a703c-4c6b-498a-bb27-7609615a74bd', prompt: 'Modern luxury kitchen island or dining table' },
  { id: 'floor-lamp', name: 'Floor Lamps', total: 100, tableId: 'tblF3ot4fdHN2VCQn', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with empty floor space for a standing floor lamp' },
  { id: 'wall-sconce', name: 'Wall Sconces', total: 100, tableId: 'tbli7nuOEhR8inzva', moodboardId: 'afa1317e-7be1-47f5-9d6f-91c7769a767d', prompt: 'Generate me a modern hallway or living room with wall sconce' },
  { id: 'table-lamp', name: 'Table Lamps', total: 100, tableId: 'tblr0uAYkDWDQZinl', moodboardId: '257569e1-7be8-4412-a90f-acbc347e4646', prompt: 'Generate me a modern bedroom with bedside table for a table lamp' },
];

// Reel Subtab 5: 1 Product, 3 Styles Reel (9:16)
export const ONE_PRODUCT_THREE_STYLES_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tbl6ls4AWcEcynBpZ', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern luxury living room with high ceiling for chandelier' },
];

// Reel Subtab 6: One at a time Lights Reel (9:16)
export const ONE_AT_A_TIME_LIGHTS_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'living-room', name: 'Bedroom', total: 100, tableId: 'tblJpEtBudQZda319', moodboardId: 'fb2487fb-2895-4d2c-9758-805aaf1bac69', prompt: 'Generate me a modern bedroom' },
];

// Reel Subtab 8: Room Build-Up Reel (9:16, ~4.8 s). One card: both rooms use the same Krea moodboard when edited here.
export const ROOM_BUILD_UP_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'room-build-up', name: 'Room Build-Up', total: 100, tableId: 'tblhq1rz9CVCD7yiR', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3' },
];

// Reel Subtab 7: Sketch to Real Reel (9:16)
export const SKETCH_TO_DRAW_REEL_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandeliers', name: 'Chandeliers', total: 100, tableId: 'tblUFR6OvFQaHnG1V', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a photo a modern luxury living room with high ceilings, clean architecture, warm natural daylight' },
  { id: 'pendant', name: 'Pendant Lights', total: 100, tableId: 'tblSALsUd5MXXnkp6', moodboardId: 'de5f4ff8-518c-4d6b-b606-ce1d5dac51f3', prompt: 'Generate me a photo a modern dining room with dining table, elegant aesthetic, soft ambient lighting' },
  { id: 'floor_lamp', name: 'Floor Lamps', total: 100, tableId: 'tblSketchToRealFloorLamps', moodboardId: 'b1641228-beec-4823-8d01-1de3eec8410d', prompt: 'Generate me a modern living room with lounge seating area, empty corner for standing floor lamp' },
  { id: 'table_lamp', name: 'Table Lamps', total: 100, tableId: 'tblSketchToRealTableLamps', moodboardId: 'fb2487fb-2895-4d2c-9758-805aaf1bac69', prompt: 'Generate me a modern bedroom with nightstand bedside table, warm contemporary interior' },
  { id: 'ceiling_mounted', name: 'Ceiling Mounted', total: 100, tableId: 'tblSketchToRealCeilingMounted', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a modern hallway or contemporary bedroom ceiling, minimalist architectural space' },
];

// Ad Covers (1:1 + 9:16 Story). All 6 lighting fixtures are wired to their dedicated Airtable tables.
export const AD_COVER_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100, tableId: 'tblwIsDGZBPuYJV2Z', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern living room', runnable: true },
  { id: 'floor-lamp', name: 'Trending Lights', total: 100, tableId: 'tbl27FKuDUD4FdJUR', moodboardId: 'c4c15a18-a92d-4465-924f-c85cfe1958bc', prompt: 'Generate me a modern living room with a standing floor lamp beside a sofa or lounge chair', runnable: true },
  { id: 'table-lamp', name: 'Table Lamp', total: 100, tableId: 'tblk3RfFqawHZ5Wrk', moodboardId: 'fb2487fb-2895-4d2c-9758-805aaf1bac69', prompt: 'Generate me a modern luxury bedroom bedside table or console with a table lamp', runnable: true },
  { id: 'cluster-chandelier', name: 'Cluster Chandelier', total: 100, tableId: 'tbltouegkjgQwdr1u', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a luxury modern room with high ceiling featuring a cluster chandelier', runnable: true },
  { id: 'pendant', name: 'Pendant Light', total: 100, tableId: 'tbl99Cwda2Xn93giT', moodboardId: '0844ad92-c34a-4dc8-9d70-d09498dc098c', prompt: 'Generate me a modern luxury dining room with hanging pendant light', runnable: true },
  { id: 'wall-light', name: 'Wall Light', total: 100, tableId: 'tblUO5nybG9fIkhTT', moodboardId: '20c3beaf-0995-44bf-a7a3-ac790fe8f315', prompt: 'Generate me a modern luxury living room with wall sconce mounted on the wall', runnable: true },
  { id: 'new-collection', name: 'New Collection', total: 100, tableId: 'tbluMexgzcWE1pDZJ', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern luxury living room', runnable: true },
  { id: 'on-sale', name: 'On Sale Designs', total: 100, tableId: 'tbleQIVBooVazAyk3', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern luxury living room with chandelier', runnable: true },
  { id: 'on-stock', name: 'On Stock Designs', total: 100, tableId: 'tblX7tpTJhfH0UXmm', moodboardId: 'de6ad512-870d-4ab7-a48c-3f3ca85faf24', prompt: 'Generate me a modern interior with ambient lighting', runnable: true },
];

// Banner Set: ONE run makes the Christmas banner (21:9: 5 fixtures blended into one Krea Christmas living room),
// the Sale banner (1800x600: dining room + kitchen, calendar captions) AND the third banner (1800x600: panel in the
// Sale colour + Krea Christmas bedroom) on ONE Airtable row. The pencils below are the Christmas living room's
// moodboard/prompt; the Sale rooms' and the third banner's moodboards/prompts are set through the SALE_BANNER_* and
// THIRD_BANNER_* env keys. The table ID comes from the AIRTABLE_TABLE_ID_CHRISTMAS_BANNER env key (default below);
// the counts endpoint returns the live value.
export const CHRISTMAS_BANNER_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'christmas_banner', name: 'Banner Set', total: 100, tableId: 'tblgNk1Tp6qKUcduw', moodboardId: 'b5ffdcbb-192e-4528-8d86-d1a4cf496887', prompt: 'Generate me a photo of a modern luxury living room with a Christmas vibe: a decorated Christmas tree, warm festive styling with garlands and soft fairy lights, a sofa and armchair seating area, a side table and console, high ceilings, clean architecture, warm cozy evening light, wide cinematic panoramic composition, with empty ceiling, wall and floor spaces for lighting fixtures', runnable: true },
];

export const DEFAULT_FIXTURES: Omit<FixtureData, 'completed'>[] = [
  { id: 'chandelier', name: 'Chandelier', total: 100 },
  { id: 'pendant', name: 'Pendant Lights', total: 100 },
  { id: 'floor-lamp', name: 'Floor Lamp', total: 100 },
  { id: 'table-lamp', name: 'Table Lamps', total: 100 },
];

/** Return the fixtures list for a specific format tab and subtab index. */
export const getFixturesForSubtab = (tab: TabType, subtabIdx: number): Omit<FixtureData, 'completed'>[] => {
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
      case 6: return ONE_AT_A_TIME_LIGHTS_REEL_FIXTURES;
      case 7: return SKETCH_TO_DRAW_REEL_FIXTURES;
      case 8: return ROOM_BUILD_UP_REEL_FIXTURES;
      default: return DEFAULT_FIXTURES;
    }
  }
  if (tab === 'adcover') return AD_COVER_FIXTURES;
  if (tab === 'banner') return CHRISTMAS_BANNER_FIXTURES;
  return DEFAULT_FIXTURES;
};

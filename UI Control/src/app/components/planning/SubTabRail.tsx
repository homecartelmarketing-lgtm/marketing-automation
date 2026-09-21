import { TabType } from './FormatTabs';

export interface SubTabCount {
  completed: number | null;
  total: number;
}

interface SubTabRailProps {
  activeTab: TabType;
  items: string[];
  activeSubTab: number;
  onSelectSubTab: (index: number) => void;
  runningSubTab?: number | null;
  counts?: SubTabCount[];
}

export function SubTabRail({
  activeTab,
  items,
  activeSubTab,
  onSelectSubTab,
  runningSubTab,
  counts,
}: SubTabRailProps) {
  // Determine active colors based on format (Feed: Yellow/Amber, Story: Light Blue/Sky, Reel: Green)
  const getActiveClass = () => {
    switch (activeTab) {
      case 'feed':
        return 'border-amber-500 text-amber-600';
      case 'story':
        return 'border-sky-500 text-sky-600';
      case 'reel':
        return 'border-emerald-600 text-emerald-600';
    }
  };

  return (
    <div className="mb-6 border-b border-gray-200">
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {items.map((item, idx) => {
          const isActive = idx === activeSubTab;
          const subCount = counts?.[idx];
          return (
            <button
              key={item + idx}
              onClick={() => onSelectSubTab(idx)}
              className={`pb-2.5 text-sm font-medium transition-all border-b-2 cursor-pointer flex items-center gap-1.5 ${
                isActive
                  ? getActiveClass()
                  : 'border-transparent text-gray-500 hover:text-gray-900 hover:border-gray-300'
              }`}
            >
              <span>{item}</span>
              {subCount && (
                <span
                  title={subCount.completed === null
                    ? `Waiting for verified Airtable completion counts in ${item}`
                    : `${subCount.completed} completed of ${subCount.total} target items in ${item}`}
                  className={`text-[11px] px-1.5 py-0.5 rounded-full font-medium tabular-nums transition-colors ${
                    isActive
                      ? activeTab === 'feed'
                        ? 'bg-amber-100 text-amber-800'
                        : activeTab === 'story'
                        ? 'bg-sky-100 text-sky-800'
                        : 'bg-emerald-100 text-emerald-800'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'
                  }`}
                >
                  {subCount.completed === null ? '—' : subCount.completed}
                </span>
              )}
              {runningSubTab === idx && (
                <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded-full animate-pulse border ${
                  activeTab === 'feed' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                  activeTab === 'story' ? 'bg-sky-100 text-sky-800 border-sky-300' :
                  'bg-emerald-100 text-emerald-800 border-emerald-300'
                }`}>
                  <span className={`inline-block w-1 h-1 rounded-full mr-1 ${
                    activeTab === 'feed' ? 'bg-amber-500' :
                    activeTab === 'story' ? 'bg-sky-500' :
                    'bg-emerald-500'
                  }`}></span>
                  Running
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

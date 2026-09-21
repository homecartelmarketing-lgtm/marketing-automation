import { useState, useEffect, useMemo } from 'react';
import {
  X,
  ExternalLink,
  Copy,
  Check,
  Search,
  Loader2,
  AlertCircle,
  Table as TableIcon,
  RefreshCw,
} from 'lucide-react';
import { FixtureData } from './FixtureCard';

export interface RowRecord {
  record_id: string;
  id: number;
  foreign_key_id: string;
  sku: string;
  item_name: string;
  status: string;
  date_and_time: string;
  thumbnail_url?: string | null;
  airtable_url: string;
}

interface RowInspectorModalProps {
  fixture: FixtureData | null;
  initialStatusFilter?: string;
  onClose: () => void;
}

export function RowInspectorModal({
  fixture,
  initialStatusFilter = 'all',
  onClose,
}: RowInspectorModalProps) {
  if (!fixture) return null;

  const [rows, setRows] = useState<RowRecord[]>([]);
  const [baseId, setBaseId] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>(initialStatusFilter.toLowerCase());
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    setActiveFilter(initialStatusFilter.toLowerCase());
  }, [initialStatusFilter]);

  const fetchRows = async (refresh: boolean = false) => {
    if (!fixture?.tableId) return;
    setIsLoading(true);
    setError(null);
    try {
      const url = `/api/rows?table_id=${fixture.tableId}${refresh ? '&refresh=true' : ''}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(`Failed to load rows: HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (data.status === 'success') {
        setRows(data.rows || []);
        if (data.base_id) setBaseId(data.base_id);
      } else {
        throw new Error(data.error || 'Failed to fetch rows');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading records');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRows(false);
  }, [fixture?.tableId]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      const normStatus = r.status.trim().toLowerCase();
      // Status filter
      if (activeFilter === 'p') {
        if (normStatus !== 'posted') return false;
      } else if (activeFilter === 's') {
        if (!['scheduled', 'schedule'].includes(normStatus)) return false;
      } else if (activeFilter === 'c') {
        if (!['complete', 'completed', 'done'].includes(normStatus)) return false;
      } else if (activeFilter === 'd') {
        if (!['discard', 'discarded'].includes(normStatus)) return false;
      } else if (activeFilter === 'fm') {
        if (!['for manual', 'for  manual', 'minor revision', 'fm'].includes(normStatus)) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        const matchFk = r.foreign_key_id.toLowerCase().includes(query);
        const matchSku = r.sku.toLowerCase().includes(query);
        const matchName = r.item_name.toLowerCase().includes(query);
        if (!matchFk && !matchSku && !matchName) return false;
      }

      return true;
    });
  }, [rows, activeFilter, searchQuery]);

  const getStatusBadge = (status: string) => {
    const s = status.trim().toLowerCase();
    if (s === 'posted') {
      return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-100 text-sky-800 border border-sky-200">Posted</span>;
    }
    if (s === 'scheduled' || s === 'schedule') {
      return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-100 text-purple-800 border border-purple-200">Scheduled</span>;
    }
    if (['complete', 'completed', 'done'].includes(s)) {
      return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">Complete</span>;
    }
    if (['discard', 'discarded'].includes(s)) {
      return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800 border border-rose-200">Discard</span>;
    }
    if (['for manual', 'for  manual', 'minor revision', 'fm'].includes(s)) {
      return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">For Manual</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-gray-100 text-gray-700 border border-gray-200">{status || 'Standby'}</span>;
  };

  const wholeTableUrl = baseId && fixture.tableId ? `https://airtable.com/${baseId}/${fixture.tableId}` : null;

  const liveCounts = useMemo(() => {
    const counts = { P: 0, S: 0, C: 0, D: 0, FM: 0 };
    for (const r of rows) {
      const s = r.status.trim().toLowerCase();
      if (['posted', 'processing', 'pending', 'in progress'].includes(s)) counts.P++;
      else if (['scheduled', 'schedule'].includes(s)) counts.S++;
      else if (['complete', 'completed', 'done', 'already attached a room interior'].includes(s)) counts.C++;
      else if (['discard', 'discarded'].includes(s)) counts.D++;
      else if (['for manual', 'for  manual', 'minor revision', 'minor revisions', 'fm'].includes(s)) counts.FM++;
    }
    return counts;
  }, [rows]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-4xl w-full flex flex-col max-h-[92vh] overflow-hidden text-gray-900 animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4 bg-gradient-to-r from-gray-50/80 to-white">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-600 shrink-0">
              <TableIcon className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-gray-900 truncate">
                  {fixture.name} — Rows Inspector
                </h3>
                <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600 border border-gray-200">
                  {fixture.tableId}
                </span>
              </div>
              <p className="text-xs text-gray-500">
                View row Foreign Key IDs and open exact Airtable records directly
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {wholeTableUrl && (
              <a
                href={wholeTableUrl}
                target="_blank"
                rel="noreferrer"
                className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200 transition-colors"
                title="Open entire table in Airtable"
              >
                <span>Airtable View</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
            <button
              onClick={() => fetchRows(true)}
              disabled={isLoading}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              title="Refresh rows"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Toolbar: Search and Filter Chips */}
        <div className="px-6 py-3 border-b border-gray-100 bg-gray-50/50 flex flex-wrap items-center justify-between gap-3">
          {/* Status Filter Chips */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFilter === 'all'
                  ? 'bg-gray-900 text-white font-semibold shadow-xs'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              All ({rows.length})
            </button>
            <button
              onClick={() => setActiveFilter('p')}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFilter === 'p'
                  ? 'bg-sky-600 text-white font-semibold shadow-xs'
                  : 'bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200'
              }`}
            >
              P: Posted ({rows.length > 0 ? liveCounts.P : (fixture.statusCounts?.P ?? 0)})
            </button>
            <button
              onClick={() => setActiveFilter('s')}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFilter === 's'
                  ? 'bg-purple-600 text-white font-semibold shadow-xs'
                  : 'bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200'
              }`}
            >
              S: Scheduled ({rows.length > 0 ? liveCounts.S : (fixture.statusCounts?.S ?? 0)})
            </button>
            <button
              onClick={() => setActiveFilter('c')}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFilter === 'c'
                  ? 'bg-emerald-600 text-white font-semibold shadow-xs'
                  : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
              }`}
            >
              C: Complete ({rows.length > 0 ? liveCounts.C : (fixture.statusCounts?.C ?? 0)})
            </button>
            <button
              onClick={() => setActiveFilter('d')}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFilter === 'd'
                  ? 'bg-rose-600 text-white font-semibold shadow-xs'
                  : 'bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200'
              }`}
            >
              D: Discard ({rows.length > 0 ? liveCounts.D : (fixture.statusCounts?.D ?? 0)})
            </button>
            <button
              onClick={() => setActiveFilter('fm')}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFilter === 'fm'
                  ? 'bg-amber-600 text-white font-semibold shadow-xs'
                  : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
              }`}
            >
              FM: For Manual ({rows.length > 0 ? liveCounts.FM : (fixture.statusCounts?.FM ?? 0)})
            </button>
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search ID, SKU, Name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
            />
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center text-gray-400 gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
              <p className="text-sm font-medium">Fetching Airtable records & Foreign Keys...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Failed to retrieve rows</p>
                <p className="text-xs text-rose-600 mt-0.5">{error}</p>
                <button
                  onClick={() => fetchRows(true)}
                  className="mt-3 text-xs font-semibold text-rose-800 underline hover:no-underline"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <TableIcon className="w-10 h-10 mx-auto mb-2 text-gray-300" />
              <p className="text-sm font-medium text-gray-600">No records found</p>
              <p className="text-xs text-gray-400 mt-1">
                {searchQuery ? `No records match "${searchQuery}"` : 'No records match the selected status filter.'}
              </p>
            </div>
          ) : (
            <div className="border border-gray-200 rounded-xl overflow-hidden shadow-2xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3">Foreign Key ID</th>
                    <th className="py-2.5 px-3">Product / SKU</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Date & Time (PHT)</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {filteredRows.map((row) => {
                    const isCopied = copiedId === row.foreign_key_id;
                    return (
                      <tr
                        key={row.record_id}
                        className="hover:bg-purple-50/30 transition-colors group"
                      >
                        {/* Foreign Key ID */}
                        <td className="py-2.5 px-3 font-mono font-bold text-gray-900 whitespace-nowrap">
                          <div className="inline-flex items-center gap-1.5 bg-gray-100 px-2 py-1 rounded-md border border-gray-200">
                            <span className="text-purple-700">{row.foreign_key_id}</span>
                            <button
                              onClick={() => handleCopy(row.foreign_key_id)}
                              className="text-gray-400 hover:text-gray-700 transition-colors"
                              title="Copy Foreign Key ID"
                            >
                              {isCopied ? (
                                <Check className="w-3 h-3 text-emerald-600" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        </td>

                        {/* Product / SKU */}
                        <td className="py-2.5 px-3">
                          <div className="flex items-center gap-2.5">
                            {row.thumbnail_url && (
                              <img
                                src={row.thumbnail_url}
                                alt={row.item_name}
                                className="w-8 h-8 rounded object-cover border border-gray-200 shrink-0"
                              />
                            )}
                            <div className="min-w-0">
                              <p className="font-semibold text-gray-900 truncate max-w-xs" title={row.item_name}>
                                {row.item_name || 'Untitled Item'}
                              </p>
                              {row.sku && (
                                <p className="font-mono text-[10px] text-gray-500 truncate">
                                  SKU: {row.sku}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          {getStatusBadge(row.status)}
                        </td>

                        {/* Date and Time */}
                        <td className="py-2.5 px-3 whitespace-nowrap text-gray-500 font-mono text-[11px]">
                          {row.date_and_time ? (
                            <span>{new Date(row.date_and_time).toLocaleString('en-US', { timeZone: 'Asia/Manila' })}</span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>

                        {/* Action Link */}
                        <td className="py-2.5 px-3 text-right whitespace-nowrap">
                          <a
                            href={row.airtable_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-gray-50 text-gray-700 hover:bg-purple-50 hover:text-purple-700 border border-gray-200 hover:border-purple-300 transition-all shadow-2xs group-hover:bg-purple-100/50"
                            title={`Open ${row.foreign_key_id} in Airtable`}
                          >
                            <span>Open in Airtable</span>
                            <ExternalLink className="w-3 h-3 text-gray-400 group-hover:text-purple-600" />
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-100 bg-gray-50 flex items-center justify-between text-xs text-gray-500">
          <span>
            Showing <strong className="text-gray-800">{filteredRows.length}</strong> of{' '}
            <strong className="text-gray-800">{rows.length}</strong> total row(s)
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

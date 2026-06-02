import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Database,
  FolderPlus,
  HardDrive,
  Image as ImageIcon,
  FolderOpen,
  Loader2,
  Play,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
} from 'lucide-react';
import './styles.css';

const DEFAULT_BACKEND = localStorage.getItem('backendUrl') || 'http://127.0.0.1:8765';

type Health = {
  ok: boolean;
  app_version: string;
  model: { name: string; version: string; dimensions: number; mode: string; fallback_reason?: string };
  index: { folders: number; images: number; last_indexed_at: string | null };
};

type Folder = { id: number; path: string; added_at: string };
type IndexStatus = {
  running: boolean;
  stage: string;
  processed: number;
  total: number;
  indexed: number;
  skipped: number;
  errors: number;
  message: string;
};
type Result = {
  id: number;
  path: string;
  filename: string;
  size: number;
  width?: number;
  height?: number;
  score: number;
  thumbnail_url: string;
};
type SearchEvent = {
  stage: string;
  progress: number;
  message: string;
  results?: Result[];
};

function App() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND);
  const [draftBackendUrl, setDraftBackendUrl] = useState(DEFAULT_BACKEND);
  const [health, setHealth] = useState<Health | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folderPath, setFolderPath] = useState('');
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [searchEvent, setSearchEvent] = useState<SearchEvent | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [notice, setNotice] = useState('');

  const connected = Boolean(health?.ok);
  const indexProgress = indexStatus?.total ? Math.round((indexStatus.processed / indexStatus.total) * 100) : 0;

  const thumbnailUrl = useMemo(() => {
    return (path: string) => `${backendUrl}${path}`;
  }, [backendUrl]);

  const selectedResults = useMemo(() => {
    const selected = new Set(selectedIds);
    return results.filter((result) => selected.has(result.id));
  }, [results, selectedIds]);

  async function api<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${backendUrl}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json() as Promise<T>;
  }

  async function refresh() {
    try {
      const [healthData, folderData, statusData] = await Promise.all([
        api<Health>('/api/health'),
        api<{ folders: Folder[] }>('/api/folders'),
        api<{ status: IndexStatus }>('/api/index/status'),
      ]);
      setHealth(healthData);
      setFolders(folderData.folders);
      setIndexStatus(statusData.status);
      setNotice('');
    } catch {
      setHealth(null);
      setNotice('Local backend is offline. Start it, then refresh the connection.');
    }
  }

  async function addFolder(event: React.FormEvent) {
    event.preventDefault();
    if (!folderPath.trim()) return;
    try {
      await api('/api/folders', { method: 'POST', body: JSON.stringify({ path: folderPath.trim() }) });
      setFolderPath('');
      await refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not add folder.');
    }
  }

  async function startIndexing() {
    try {
      await api('/api/index', { method: 'POST' });
      await refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not start indexing.');
    }
  }

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim() || isSearching) return;
      setIsSearching(true);
      setSearchEvent({ stage: 'queued', progress: 5, message: 'Starting search' });
      setResults([]);
      setSelectedIds([]);

    try {
      const response = await fetch(`${backendUrl}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 48 }),
      });
      if (!response.ok || !response.body) throw new Error('Search request failed.');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() || '';
        for (const chunk of chunks) {
          const line = chunk.split('\n').find((item) => item.startsWith('data: '));
          if (!line) continue;
          const payload = JSON.parse(line.replace('data: ', '')) as SearchEvent;
          setSearchEvent(payload);
          if (payload.results) setResults(payload.results);
        }
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Search failed.');
      setSearchEvent({ stage: 'error', progress: 100, message: 'Search failed' });
    } finally {
      setIsSearching(false);
    }
  }

  async function openResult(id: number) {
    try {
      await api(`/api/images/${id}/open`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not open image.');
    }
  }

  async function revealResult(id: number) {
    try {
      await api(`/api/images/${id}/reveal`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not reveal image in folder.');
    }
  }

  function toggleSelected(id: number) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => window.clearInterval(timer);
  }, [backendUrl]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Search size={24} />
          </div>
          <div>
            <h1>Local AI Image Search</h1>
            <p>App v{__APP_VERSION__}</p>
          </div>
        </div>

        <section className="panel compact">
          <div className="panel-title">
            <HardDrive size={16} />
            <span>Local Backend</span>
          </div>
          <div className={`status-pill ${connected ? 'ok' : 'bad'}`}>
            {connected ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
            {connected ? 'Connected' : 'Offline'}
          </div>
          <label className="field-label" htmlFor="backend-url">
            Backend URL
          </label>
          <div className="inline-control">
            <input
              id="backend-url"
              value={draftBackendUrl}
              onChange={(event) => setDraftBackendUrl(event.target.value)}
              spellCheck={false}
            />
            <button
              className="icon-button"
              title="Save backend URL"
              onClick={() => {
                localStorage.setItem('backendUrl', draftBackendUrl);
                setBackendUrl(draftBackendUrl);
              }}
            >
              <Settings size={17} />
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <FolderPlus size={16} />
            <span>Folders</span>
          </div>
          <form onSubmit={addFolder} className="stack">
            <input
              value={folderPath}
              onChange={(event) => setFolderPath(event.target.value)}
              placeholder="G:\\Photos\\Family"
              aria-label="Folder path"
            />
            <button className="primary subtle" type="submit">
              <FolderPlus size={17} />
              Add Folder
            </button>
          </form>
          <div className="folder-list">
            {folders.length === 0 ? (
              <p className="muted">No folders added yet.</p>
            ) : (
              folders.map((folder) => <div key={folder.id} className="folder-row" title={folder.path}>{folder.path}</div>)
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Database size={16} />
            <span>Index</span>
          </div>
          <div className="metric-row">
            <span>Images</span>
            <strong>{health?.index.images ?? 0}</strong>
          </div>
          <div className="metric-row">
            <span>Folders</span>
            <strong>{health?.index.folders ?? 0}</strong>
          </div>
          <div className="metric-row">
            <span>Model</span>
            <strong>{health?.model.name ?? 'Unavailable'}</strong>
          </div>
          <ProgressBar value={indexProgress} active={Boolean(indexStatus?.running)} label={indexStatus?.message || 'Idle'} />
          <button className="primary" onClick={startIndexing} disabled={!connected || Boolean(indexStatus?.running)}>
            {indexStatus?.running ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
            {indexStatus?.running ? 'Indexing' : 'Rebuild Index'}
          </button>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyeline">Private local search</p>
            <h2>Find a specific image by describing it.</h2>
          </div>
          <div className="version-card">
            <span>Frontend v{__APP_VERSION__}</span>
            <span>Backend v{health?.app_version ?? '-'}</span>
          </div>
        </header>

        {notice ? <div className="notice">{notice}</div> : null}
        {health?.model.fallback_reason ? (
          <div className="notice warning">
            Running fallback search model. Natural-language results will be poor until local CLIP dependencies are installed
            and the index is rebuilt.
          </div>
        ) : null}

        <form className="search-box" onSubmit={runSearch}>
          <Sparkles size={22} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Example: person in a red coat near a lake"
            aria-label="Search images"
          />
          <button className="search-button" disabled={!connected || !query.trim() || isSearching}>
            {isSearching ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            Search
          </button>
        </form>

        <ProgressBar
          value={searchEvent?.progress ?? 0}
          active={isSearching}
          label={searchEvent?.message || 'Search stages appear here'}
          stage={searchEvent?.stage}
          large
        />

        <div className="results-header">
          <div>
            <h3>Results</h3>
            <p>{results.length ? `${results.length} matches ranked by local similarity` : 'Search results will appear here.'}</p>
          </div>
          <button className="secondary" onClick={refresh}>
            <Activity size={17} />
            Refresh
          </button>
        </div>

        {selectedResults.length ? (
          <section className="selection-panel" aria-label="Selected images">
            <div className="selection-heading">
              <div>
                <h3>Selected</h3>
                <p>{selectedResults.length} image{selectedResults.length === 1 ? '' : 's'}</p>
              </div>
              <button className="secondary" onClick={() => setSelectedIds([])}>
                Clear
              </button>
            </div>
            <div className="selected-list">
              {selectedResults.map((result) => (
                <article className="selected-row" key={result.id}>
                  <img src={thumbnailUrl(result.thumbnail_url)} alt="" />
                  <div>
                    <strong>{result.filename}</strong>
                    <span title={result.path}>{result.path}</span>
                  </div>
                  <button className="secondary" onClick={() => openResult(result.id)}>
                    <ImageIcon size={16} />
                    Open
                  </button>
                  <button className="secondary" onClick={() => revealResult(result.id)}>
                    <FolderOpen size={16} />
                    Open in Folder
                  </button>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section className="results-grid">
          {results.length === 0 ? (
            <div className="empty-state">
              <ImageIcon size={44} />
              <h3>Ready for your photo library</h3>
              <p>Add a folder, rebuild the index, then describe the image you want to find.</p>
              <button className="primary" onClick={startIndexing} disabled={!connected}>
                <Play size={17} />
                Start Index
              </button>
            </div>
          ) : (
            results.map((result) => (
              <article className={`result-card ${selectedIds.includes(result.id) ? 'selected' : ''}`} key={result.id}>
                <button className="image-button" onClick={() => toggleSelected(result.id)} title="Select image">
                  <img src={thumbnailUrl(result.thumbnail_url)} alt={result.filename} loading="lazy" />
                </button>
                <div className="result-body">
                  <strong title={result.filename}>{result.filename}</strong>
                  <span title={result.path}>{result.path}</span>
                  <div className="score-line">
                    <span>{result.width && result.height ? `${result.width} x ${result.height}` : 'Image'}</span>
                    <span>{Math.max(0, result.score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="result-actions">
                    <button className="secondary" onClick={() => openResult(result.id)}>
                      <ImageIcon size={15} />
                      Open
                    </button>
                    <button className="secondary" onClick={() => revealResult(result.id)}>
                      <FolderOpen size={15} />
                      Folder
                    </button>
                  </div>
                </div>
              </article>
            ))
          )}
        </section>
      </section>
    </main>
  );
}

function ProgressBar({ value, active, label, stage, large = false }: { value: number; active: boolean; label: string; stage?: string; large?: boolean }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={`progress-wrap ${large ? 'large' : ''}`}>
      <div className="progress-meta">
        <span>{label}</span>
        <strong>{stage ? `${stage} · ` : ''}{clamped}%</strong>
      </div>
      <div className={`progress-track ${active ? 'active' : ''}`}>
        <div className="progress-fill" style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

import { useState, useEffect } from 'react';
import { Activity, ShieldAlert, GitBranch, Network, Settings, TerminalSquare, AlertTriangle } from 'lucide-react';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState({ score: 100, drift: 0, exploits_prevented: 0 });
  const [recentScans, setRecentScans] = useState<any[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<any[]>([]);

  const [isConfigured, setIsConfigured] = useState(() => {
    return localStorage.getItem('sentinel_configured') === 'true';
  });
  const [repoUrl, setRepoUrl] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [aiStatus, setAiStatus] = useState({ mistral: 'checking', qwen: 'checking' });
  const [scanProgress, setScanProgress] = useState(0);
  const [, setPrevScanCount] = useState(-1);
  const [selectedScan, setSelectedScan] = useState<any>(null);

  // Only fetches live scan data — no AI status spam
  const fetchDashboard = () => {
    fetch('/api/dashboard/stats').then(r => r.json()).then(setStats).catch(() => { });
    fetch('/api/dashboard/recent_scans').then(r => r.json()).then(d => {
      if (Array.isArray(d)) {
        setRecentScans(d);
        setPrevScanCount(prev => {
          if (prev >= 0 && d.length > prev) setScanProgress(0);
          return d.length;
        });
      }
    }).catch(() => { });
    fetch('/api/dashboard/vulnerabilities').then(r => r.json()).then(d => { if (Array.isArray(d)) setVulnerabilities(d); }).catch(() => { });
  };

  const clearHistory = () => {
    if (!confirm('Clear all scan history? This cannot be undone.')) return;
    fetch('/api/dashboard/reset', { method: 'POST' })
      .then(() => {
        setStats({ score: 100, drift: 0, exploits_prevented: 0 });
        setRecentScans([]);
        setVulnerabilities([]);
        setScanProgress(0);
        localStorage.removeItem('sentinel_configured');
        setIsConfigured(false);
      })
      .catch(() => {
        // Reset locally anyway
        setStats({ score: 100, drift: 0, exploits_prevented: 0 });
        setRecentScans([]);
        setVulnerabilities([]);
        setScanProgress(0);
        localStorage.removeItem('sentinel_configured');
        setIsConfigured(false);
      });
  };

  // While scanning: poll every 4s for results AND advance the bar.
  // The instant recentScans count grows, the bar is dismissed.
  useEffect(() => {
    if (scanProgress <= 0) return;

    const tick = setInterval(() => {
      // Advance bar smoothly (caps at 98 so it never "finishes" on its own)
      setScanProgress(p => (p >= 98 ? 98 : Math.min(98, p + (100 / 90) * 4)));

      // Check if backend has new results
      fetch('/api/dashboard/recent_scans')
        .then(r => r.json())
        .then(d => {
          if (!Array.isArray(d)) return;
          setRecentScans(prev => {
            if (d.length > prev.length) {
              // New results arrived — dismiss bar and refresh everything
              setScanProgress(0);
              fetchDashboard();
            }
            return d;
          });
        })
        .catch(() => { });
    }, 4000);

    return () => clearInterval(tick);
  }, [scanProgress > 0]);

  useEffect(() => {
    // Fetch everything once on boot — no polling
    fetch('/api/dashboard/ai_status').then(r => r.json()).then(setAiStatus).catch(() => setAiStatus({ mistral: 'offline', qwen: 'offline' }));
    fetchDashboard();
  }, []);

  if (!isConfigured) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50 font-sans flex items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none"></div>
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none translate-y-1/2 -translate-x-1/2"></div>

        <div className="z-10 bg-slate-900/40 border border-slate-800/60 rounded-2xl p-8 backdrop-blur-md shadow-2xl max-w-md w-full mx-4 relative overflow-hidden">
          <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-emerald-500 to-blue-500"></div>
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-full bg-slate-800/80 border border-slate-700 flex items-center justify-center shadow-lg">
              <ShieldAlert className="text-emerald-400 w-8 h-8" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-center text-slate-200 mb-2">Connect Repository</h2>
          <p className="text-center text-slate-400 text-sm mb-6">Enter a GitHub repository URL to begin continuous authorization analysis.</p>

          <div className="flex justify-center gap-4 mb-8">
            <div className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2 ${aiStatus.mistral === 'online' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : aiStatus.mistral === 'checking' ? 'bg-slate-800 border border-slate-700 text-slate-400' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${aiStatus.mistral === 'online' ? 'bg-emerald-400 animate-pulse' : aiStatus.mistral === 'checking' ? 'bg-slate-500' : 'bg-red-500'}`}></span>
              Mistral: {aiStatus.mistral}
            </div>
            <div className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2 ${aiStatus.qwen === 'online' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : aiStatus.qwen === 'checking' ? 'bg-slate-800 border border-slate-700 text-slate-400' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${aiStatus.qwen === 'online' ? 'bg-emerald-400 animate-pulse' : aiStatus.qwen === 'checking' ? 'bg-slate-500' : 'bg-red-500'}`}></span>
              Qwen: {aiStatus.qwen}
            </div>
          </div>

          <form onSubmit={(e) => {
            e.preventDefault();
            if (!repoUrl) return;
            setIsScanning(true);
            fetch('/api/scan', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ github_url: repoUrl })
            }).then(() => {
              setIsScanning(false);
              setScanProgress(2); // kick off the progress bar
              setIsConfigured(true);
              localStorage.setItem('sentinel_configured', 'true');
            }).catch(() => {
              setIsScanning(false);
              setScanProgress(2);
              setIsConfigured(true);
              localStorage.setItem('sentinel_configured', 'true');
            });
          }}>
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-400 mb-2">GitHub URL</label>
              <input
                type="url"
                value={repoUrl}
                onChange={e => setRepoUrl(e.target.value)}
                placeholder="https://github.com/my-org/my-repo"
                className="w-full bg-slate-950/50 border border-slate-800 rounded-xl px-4 py-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50 transition-colors"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isScanning || !repoUrl}
              className="w-full bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-slate-950 font-semibold py-3 rounded-xl transition-all disabled:opacity-50 flex justify-center items-center shadow-lg"
            >
              {isScanning ? 'Connecting to Engine...' : 'Initialize Sentinel'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans flex overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 border-r border-slate-800 bg-slate-900/50 backdrop-blur-xl flex flex-col">
        <div className="p-6">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-blue-500 bg-clip-text text-transparent flex items-center gap-2">
            <ShieldAlert className="text-emerald-400" />
            Sentinel AI
          </h1>
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Continuous Security</p>
        </div>

        <nav className="flex-1 px-4 space-y-2 mt-4">
          <button
            onClick={() => setActiveTab('overview')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'overview' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
          >
            <Activity size={18} />
            Overview
          </button>
          <button
            onClick={() => setActiveTab('graph')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'graph' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
          >
            <Network size={18} />
            Auth Graph
          </button>
          <button
            onClick={() => setActiveTab('pr')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'pr' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
          >
            <GitBranch size={18} />
            PR Scans
          </button>
        </nav>

        <div className="p-4 border-t border-slate-800">
          <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-all">
            <Settings size={18} />
            Settings
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col relative overflow-y-auto">
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none"></div>
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none translate-y-1/2 -translate-x-1/2"></div>

        {/* Header */}
        <header className="h-20 border-b border-slate-800/50 flex items-center justify-between px-8 bg-slate-900/20 backdrop-blur-sm z-10">
          <h2 className="text-xl font-medium text-slate-200 capitalize">{activeTab.replace('_', ' ')}</h2>
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                setIsConfigured(false);
                localStorage.removeItem('sentinel_configured');
              }}
              className="px-4 py-1.5 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors"
            >
              + Scan New Repo
            </button>
            <button
              onClick={clearHistory}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all"
              title="Clear all scan history and reset dashboard"
            >
              Clear History
            </button>
            <div className="px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium flex items-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.15)]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Agents Active
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-slate-800 to-slate-700 border border-slate-600 flex items-center justify-center">
              <TerminalSquare size={18} className="text-slate-300" />
            </div>
          </div>
        </header>

        {/* AI Inference Progress Bar */}
        {scanProgress > 0 && (
          <div className="mx-8 mt-4 bg-slate-900/60 border border-emerald-500/20 rounded-xl p-4 backdrop-blur-md z-10">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-emerald-400 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block" />
                {scanProgress < 15 ? 'Downloading repository...' :
                  scanProgress < 35 ? 'Parsing AST & extracting endpoints...' :
                    scanProgress < 70 ? 'Running AI security analysis (Mistral + Qwen)...' :
                      'Generating security report...'}
              </span>
              <span className="text-xs text-slate-400">{Math.round(scanProgress)}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-blue-400 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.6)] transition-all duration-1000 ease-linear"
                style={{ width: `${scanProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Dashboard Content */}
        <main className="flex-1 p-8 z-10 w-full max-w-7xl mx-auto space-y-6">

          {/* Top Stats Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl hover:border-emerald-500/30 transition-all group overflow-hidden relative">
              <div className="absolute -right-6 -top-6 w-24 h-24 bg-emerald-500/10 rounded-full blur-xl group-hover:bg-emerald-500/20 transition-all"></div>
              <h3 className="text-slate-400 text-sm font-medium mb-2">Auth Integrity Score</h3>
              <div className="flex items-end gap-3">
                <span className="text-5xl font-bold text-emerald-400">{stats.score}</span>
                <span className="text-emerald-500 text-sm mb-1 font-medium bg-emerald-500/10 px-2 py-0.5 rounded-md">+4 from last week</span>
              </div>
            </div>

            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl hover:border-blue-500/30 transition-all group overflow-hidden relative">
              <div className="absolute -right-6 -top-6 w-24 h-24 bg-blue-500/10 rounded-full blur-xl group-hover:bg-blue-500/20 transition-all"></div>
              <h3 className="text-slate-400 text-sm font-medium mb-2">Drift Delta</h3>
              <div className="flex items-end gap-3">
                <span className="text-5xl font-bold text-blue-400">{stats.drift}</span>
                <span className="text-slate-400 text-sm mb-1 font-medium">routes modified</span>
              </div>
            </div>

            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl hover:border-red-500/30 transition-all group overflow-hidden relative">
              <div className="absolute -right-6 -top-6 w-24 h-24 bg-red-500/10 rounded-full blur-xl group-hover:bg-red-500/20 transition-all"></div>
              <h3 className="text-slate-400 text-sm font-medium mb-2">Active Exploits Prevented</h3>
              <div className="flex items-end gap-3">
                <span className="text-5xl font-bold text-slate-100">{stats.exploits_prevented}</span>
                <span className="text-red-400 text-sm mb-1 font-medium flex items-center gap-1 bg-red-400/10 px-2 py-0.5 rounded-md"><AlertTriangle size={14} /> 1 BOLA attempt</span>
              </div>
            </div>
          </div>

          {/* Graph Visualization Mock */}
          <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl h-96 flex flex-col relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-emerald-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-duration-500"></div>
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="text-lg font-medium text-slate-200">Authorization Graph</h3>
                <p className="text-sm text-slate-500">Role &rarr; Route &rarr; Resource Mapping</p>
              </div>
              <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-sm rounded-lg transition-colors border border-slate-700 font-medium">
                Open Full Graph
              </button>
            </div>

            <div className="flex-1 border border-slate-800/50 rounded-xl bg-slate-950/50 flex items-center justify-center relative overflow-hidden">
              {/* Mock Graph Visuals */}
              <div className="absolute inset-0 pattern-grid-lg text-slate-800/20 opacity-50"></div>
              <div className="relative z-10 flex items-center gap-8 text-sm font-medium">
                <div className="px-4 py-2 bg-blue-500/10 border border-blue-500/40 text-blue-400 rounded-lg shadow-[0_0_20px_rgba(59,130,246,0.1)]">User Role</div>
                <div className="h-px w-16 bg-gradient-to-r from-blue-500/40 to-slate-600 relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-slate-500"></div>
                </div>
                <div className="px-4 py-2 bg-slate-800 border border-slate-700 text-slate-300 rounded-lg">GET /api/user/{'{id}'}</div>
                <div className="h-px w-16 bg-gradient-to-r from-slate-600 to-emerald-500/40 relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)]"></div>
                </div>
                <div className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 rounded-lg shadow-[0_0_20px_rgba(16,185,129,0.1)]">User Profile Data</div>
              </div>

              {/* Exploit path mock */}
              <div className="absolute top-1/4 left-1/3 w-1/3 flex items-center gap-4 text-xs font-medium opacity-60 hover:opacity-100 transition-opacity cursor-pointer">
                <div className="px-3 py-1 bg-red-500/10 border border-red-500/40 text-red-400 rounded-lg">Suspicious Role</div>
                <svg className="w-16 h-8 text-red-500/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"></path></svg>
              </div>
            </div>
          </div>

          {/* Recent Findings */}
          <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl">
            <h3 className="text-lg font-medium text-slate-200 mb-6">Recent PR Core Analysis</h3>
            <div className="space-y-4">
              {recentScans.map((pr, i) => (
                <div key={i} className="flex items-center justify-between p-4 rounded-xl bg-slate-800/30 border border-slate-800 hover:bg-slate-800/50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className={`w-2 h-2 rounded-full ${pr.status === 'Passed' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]'}`}></div>
                    <div>
                      <p className="font-medium text-slate-200">{pr.title} <span className="text-slate-500 text-sm font-normal ml-2">{pr.id}</span></p>
                      <p className="text-sm text-slate-500 mt-1">{pr.time}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    {pr.issues > 0 ? (
                      <span className="flex items-center gap-1.5 text-sm font-medium text-red-400 bg-red-400/10 px-3 py-1 rounded-full"><AlertTriangle size={14} /> {pr.issues} Findings</span>
                    ) : (
                      <span className="text-sm text-emerald-500 font-medium">Clean</span>
                    )}
                    <button
                      onClick={() => setSelectedScan(pr)}
                      className="text-emerald-400 hover:text-emerald-300 text-sm font-medium transition-colors"
                    >
                      View Details →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Vulnerabilities Panel */}
          <div className="bg-slate-900/40 border border-red-900/30 rounded-2xl p-6 backdrop-blur-md shadow-xl">
            <h3 className="text-lg font-medium text-slate-200 mb-2 flex items-center gap-2">
              <AlertTriangle size={18} className="text-red-400" />
              Detected Vulnerabilities
              {vulnerabilities.length > 0 && (
                <span className="ml-2 px-2 py-0.5 rounded-full text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/30">{vulnerabilities.length}</span>
              )}
            </h3>
            {vulnerabilities.length === 0 ? (
              <p className="text-slate-500 text-sm mt-4">No vulnerabilities detected yet. Run a scan to see findings here.</p>
            ) : (
              <div className="space-y-3 mt-4">
                {vulnerabilities.map((v, i) => (
                  <div key={i} className="p-4 rounded-xl bg-red-950/20 border border-red-800/30 hover:border-red-600/40 transition-all">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full mr-2 ${v.vulnerability_type === 'BOLA' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                          {v.vulnerability_type}
                        </span>
                        <span className="text-sm font-mono text-slate-300">{v.method} {v.path}</span>
                        <span className="ml-2 text-xs text-slate-500">in {v.function_name}()</span>
                      </div>
                      <span className="text-xs text-slate-400 whitespace-nowrap">Confidence: {v.confidence}%</span>
                    </div>
                    {v.reasoning && <p className="text-xs text-slate-400 mt-2 leading-relaxed">{v.reasoning}</p>}
                    <p className="text-xs text-slate-600 mt-1">Repo: {v.repo} • {v.scan_time}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

        </main>
      </div>

      {/* View Details Modal */}
      {selectedScan && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => setSelectedScan(null)}
        >
          <div
            className="relative bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-start justify-between mb-5">
              <div>
                <h3 className="text-lg font-semibold text-slate-200">{selectedScan.title}</h3>
                <p className="text-sm text-slate-500 mt-0.5">{selectedScan.id} · {selectedScan.time}</p>
              </div>
              <button
                onClick={() => setSelectedScan(null)}
                className="text-slate-500 hover:text-slate-300 text-xl leading-none px-2"
              >✕</button>
            </div>

            {/* Score badge */}
            <div className="flex items-center gap-3 mb-5">
              <span className={`px-3 py-1 rounded-full text-sm font-bold border ${selectedScan.status === 'Passed'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-red-500/10 text-red-400 border-red-500/30'
                }`}>
                {selectedScan.status}
              </span>
              {selectedScan.issues > 0 && (
                <span className="text-sm text-red-400 font-medium flex items-center gap-1">
                  <AlertTriangle size={14} /> {selectedScan.issues} Finding{selectedScan.issues > 1 ? 's' : ''}
                </span>
              )}
            </div>

            {/* Vulnerability list */}
            {(() => {
              const vulns = (() => {
                try {
                  const v = selectedScan.vulnerabilities;
                  return Array.isArray(v) ? v : (typeof v === 'string' ? JSON.parse(v) : []);
                } catch { return []; }
              })();
              return vulns.length === 0 ? (
                <div className="text-center py-8">
                  <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-3">
                    <span className="text-emerald-400 text-xl">✓</span>
                  </div>
                  <p className="text-slate-400 text-sm">No vulnerabilities found in this scan.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {vulns.map((v: any, i: number) => (
                    <div key={i} className="p-4 rounded-xl bg-red-950/20 border border-red-800/30 hover:border-red-600/40 transition-all">
                      <div className="flex items-start justify-between gap-4 mb-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${v.vulnerability_type === 'BOLA' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30'
                            : v.vulnerability_type === 'IDOR' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                              : v.vulnerability_type === 'Privilege Escalation' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                                : 'bg-red-500/20 text-red-400 border-red-500/30'
                            }`}>{v.vulnerability_type}</span>
                          <span className="text-sm font-mono text-slate-300">{v.function_name}()</span>
                        </div>
                        <span className="text-xs text-slate-400 whitespace-nowrap">Confidence: <span className="text-slate-200 font-semibold">{v.confidence}%</span></span>
                      </div>
                      {v.reasoning && <p className="text-xs text-slate-400 leading-relaxed">{v.reasoning}</p>}
                      {v.file_path && <p className="text-xs text-slate-600 mt-2 font-mono">{v.file_path}</p>}
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Pattern def for graph background */}
      <style>{`
        .pattern-grid-lg {
          background-image: linear-gradient(to right, currentColor 1px, transparent 1px),
          linear-gradient(to bottom, currentColor 1px, transparent 1px);
          background-size: 40px 40px;
        }
      `}</style>
    </div>
  );
}

export default App;

import { useState, useEffect } from 'react';
import { Activity, ShieldAlert, GitBranch, Network, Settings, TerminalSquare, AlertTriangle } from 'lucide-react';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState({ score: 92, drift: 2, exploits_prevented: 14 });
  const [recentScans, setRecentScans] = useState([
    { id: '#420', status: 'Passed', title: 'Refactor user routing', issues: 0, time: '2h ago' },
    { id: '#419', status: 'Blocked', title: 'Add admin dashboard metrics', issues: 2, time: '5h ago' },
    { id: '#418', status: 'Passed', title: 'Update dependency injection', issues: 0, time: '1d ago' },
  ]);

  const [isConfigured, setIsConfigured] = useState(() => {
    return localStorage.getItem('sentinel_configured') === 'true';
  });
  const [repoUrl, setRepoUrl] = useState('');
  const [isScanning, setIsScanning] = useState(false);

  useEffect(() => {
    // Fetch dashboard stats from backend
    fetch('/api/dashboard/stats')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Error fetching stats:", err));

    // Fetch recent PR scans from backend
    fetch('/api/dashboard/recent_scans')
      .then(res => res.json())
      .then(data => setRecentScans(data))
      .catch(err => console.error("Error fetching recent scans:", err));
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
          <p className="text-center text-slate-400 text-sm mb-8">Enter a GitHub repository URL to begin continuous authorization analysis.</p>

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
              setIsConfigured(true);
              localStorage.setItem('sentinel_configured', 'true');
            }).catch(() => {
              setIsScanning(false);
              setIsConfigured(true); // Proceed anyway for MVP testing
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
            <div className="px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium flex items-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.15)]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Agents Active
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-slate-800 to-slate-700 border border-slate-600 flex items-center justify-center">
              <TerminalSquare size={18} className="text-slate-300" />
            </div>
          </div>
        </header>

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
                    <button className="text-slate-400 hover:text-slate-300">View Details &rarr;</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </main>
      </div>

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

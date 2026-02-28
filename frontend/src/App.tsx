import { useState, useEffect, useRef } from 'react';
import { Activity, ShieldAlert, GitBranch, Settings, TerminalSquare, AlertTriangle, Swords, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

interface AttackResult {
  attack_name: string;
  attack_description: string;
  target_endpoint: string;
  target_method: string;
  vulnerability_title: string;
  original_severity: string;
  attack_successful: boolean;
  exploitation_difficulty: string;
  simulated_at: string;
  recommendation: string;
  model_source: string;
  validated_by: string;
  confidence: number;
}

interface RedTeamResult {
  status: string;
  timestamp: string;
  model_source: string;
  summary: {
    model?: string;
    vulnerabilities_analyzed: number;
    total_attacks_simulated: number;
    successful_attacks: number;
    findings_created: number;
  };
  attack_results: AttackResult[];
  high_risk_findings: AttackResult[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

function severityClass(sev: string) {
  return SEVERITY_COLORS[sev?.toLowerCase()] ?? SEVERITY_COLORS.info;
}

// ── Red Team Panel ────────────────────────────────────────────────────────────

function RedTeamPanel({ aiStatus }: { aiStatus: { mistral: string; qwen: string } }) {
  const [qwenResult, setQwenResult] = useState<RedTeamResult | null>(null);
  const [mistralResult, setMistralResult] = useState<RedTeamResult | null>(null);
  const [loadingQwen, setLoadingQwen] = useState(false);
  const [loadingMistral, setLoadingMistral] = useState(false);
  const [loadingCombined, setLoadingCombined] = useState(false);
  const [combinedResult, setCombinedResult] = useState<RedTeamResult | null>(null);
  const [expandedQwen, setExpandedQwen] = useState(true);
  const [expandedMistral, setExpandedMistral] = useState(true);

  const runPipeline = async (model: 'qwen' | 'mistral' | 'combined') => {
    const endpoint =
      model === 'combined'
        ? '/api/v1/attacks/simulate'
        : `/api/v1/attacks/simulate/${model}`;

    if (model === 'qwen') setLoadingQwen(true);
    else if (model === 'mistral') setLoadingMistral(true);
    else setLoadingCombined(true);

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ store_findings: true }),
      });
      const data: RedTeamResult = await res.json();
      if (model === 'qwen') setQwenResult(data);
      else if (model === 'mistral') setMistralResult(data);
      else setCombinedResult(data);
    } catch (e) {
      console.error(`Red team ${model} failed`, e);
    } finally {
      if (model === 'qwen') setLoadingQwen(false);
      else if (model === 'mistral') setLoadingMistral(false);
      else setLoadingCombined(false);
    }
  };

  const ModelBadge = ({ name, status }: { name: string; status: string }) => (
    <div
      className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2 border ${status === 'online'
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        : status === 'checking'
          ? 'bg-slate-800 border-slate-700 text-slate-400'
          : 'bg-red-500/10 text-red-400 border-red-500/20'
        }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${status === 'online'
          ? 'bg-emerald-400 animate-pulse'
          : status === 'checking'
            ? 'bg-slate-500'
            : 'bg-red-500'
          }`}
      />
      {name}: {status}
    </div>
  );

  const SummaryCard = ({
    result,
    model,
    loading,
    expanded,
    onToggle,
  }: {
    result: RedTeamResult | null;
    model: 'qwen' | 'mistral';
    loading: boolean;
    expanded: boolean;
    onToggle: () => void;
  }) => {
    const glow = model === 'qwen' ? 'bg-purple-500/10' : 'bg-blue-500/10';
    const border = model === 'qwen' ? 'hover:border-purple-500/30' : 'hover:border-blue-500/30';
    const textColor = model === 'qwen' ? 'text-purple-400' : 'text-blue-400';
    const badgeBg = model === 'qwen' ? 'bg-purple-500/10 border-purple-500/20 text-purple-300' : 'bg-blue-500/10 border-blue-500/20 text-blue-300';

    return (
      <div
        className={`flex-1 bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl ${border} transition-all relative overflow-hidden`}
      >
        <div className={`absolute -right-6 -top-6 w-24 h-24 ${glow} rounded-full blur-xl`} />
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-lg ${model === 'qwen' ? 'bg-purple-500/15' : 'bg-blue-500/15'} border ${model === 'qwen' ? 'border-purple-500/20' : 'border-blue-500/20'} flex items-center justify-center`}>
              <Swords size={15} className={textColor} />
            </div>
            <div>
              <h4 className="font-semibold text-slate-200 capitalize">{model} Red Team</h4>
              <p className="text-xs text-slate-500">Attack simulation via {model} findings</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full border ${badgeBg}`}>{model.toUpperCase()}</span>
            <button
              onClick={onToggle}
              className="text-slate-500 hover:text-slate-300 transition-colors p-1"
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>
        </div>

        {/* Run button */}
        <button
          onClick={() => runPipeline(model)}
          disabled={loading}
          className={`w-full mb-4 py-2.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all ${loading
            ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            : model === 'qwen'
              ? 'bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 text-white shadow-lg shadow-purple-500/10'
              : 'bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white shadow-lg shadow-blue-500/10'
            }`}
        >
          {loading ? (
            <>
              <Loader2 size={15} className="animate-spin" />
              Running {model} pipeline…
            </>
          ) : (
            <>
              <Swords size={15} />
              Run {model.toUpperCase()} Red Team
            </>
          )}
        </button>

        {/* Results */}
        {result && expanded && (
          <>
            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              {[
                { label: 'Vulns Analyzed', value: result.summary.vulnerabilities_analyzed },
                { label: 'Attacks Run', value: result.summary.total_attacks_simulated },
                { label: 'Exploits Found', value: result.summary.successful_attacks },
              ].map(({ label, value }) => (
                <div key={label} className="bg-slate-950/40 rounded-xl p-3 text-center border border-slate-800/50">
                  <p className={`text-2xl font-bold ${textColor}`}>{value}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {/* Attack list */}
            {result.attack_results.length === 0 ? (
              <div className="text-center py-6 text-slate-500 text-sm">
                No vulnerabilities found for {model}. Run a scan first.
              </div>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1 custom-scrollbar">
                {result.attack_results.map((attack, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-xl border transition-colors ${attack.attack_successful
                      ? 'bg-red-950/20 border-red-800/30 hover:border-red-600/40'
                      : 'bg-slate-800/20 border-slate-700/30 hover:border-slate-600/40'
                      }`}
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        {attack.attack_successful ? (
                          <XCircle size={13} className="text-red-400 flex-shrink-0" />
                        ) : (
                          <CheckCircle size={13} className="text-emerald-400 flex-shrink-0" />
                        )}
                        <span className="text-xs font-semibold text-slate-200">{attack.attack_name}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded-full border ${severityClass(attack.original_severity)}`}>
                          {attack.original_severity}
                        </span>
                        <span className="text-xs text-slate-500 bg-slate-800/50 px-1.5 py-0.5 rounded border border-slate-700/50">
                          {attack.exploitation_difficulty}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500 font-mono whitespace-nowrap">
                        {attack.target_method} {attack.target_endpoint}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">{attack.attack_description}</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* No result yet & not loading */}
        {!result && !loading && (
          <div className="text-center py-8 text-slate-600 text-sm">
            Click the button above to run the {model.toUpperCase()} pipeline
          </div>
        )}
      </div>
    );
  };

  // All findings merged from both model results
  const allFindings: (AttackResult & { _model: string })[] = [
    ...(qwenResult?.attack_results ?? []).map((r) => ({ ...r, _model: 'qwen' })),
    ...(mistralResult?.attack_results ?? []).map((r) => ({ ...r, _model: 'mistral' })),
    ...(combinedResult?.attack_results ?? []).map((r) => ({ ...r, _model: 'combined' })),
  ].filter((r) => r.attack_successful);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-slate-200 flex items-center gap-2">
            <Swords size={20} className="text-red-400" />
            Red Team Attack Simulation
          </h3>
          <p className="text-sm text-slate-500 mt-1">
            Run adversarial attack pipelines using Qwen and Mistral–detected vulnerabilities
          </p>
        </div>
        {/* Live model status */}
        <div className="flex items-center gap-3">
          <ModelBadge name="Mistral" status={aiStatus.mistral} />
          <ModelBadge name="Qwen" status={aiStatus.qwen} />
        </div>
      </div>

      {/* Per-model cards */}
      <div className="flex flex-col md:flex-row gap-6">
        <SummaryCard
          result={qwenResult}
          model="qwen"
          loading={loadingQwen}
          expanded={expandedQwen}
          onToggle={() => setExpandedQwen((p) => !p)}
        />
        <SummaryCard
          result={mistralResult}
          model="mistral"
          loading={loadingMistral}
          expanded={expandedMistral}
          onToggle={() => setExpandedMistral((p) => !p)}
        />
      </div>

      {/* Combined pipeline */}
      <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl hover:border-emerald-500/20 transition-all relative overflow-hidden">
        <div className="absolute -right-6 -top-6 w-24 h-24 bg-emerald-500/10 rounded-full blur-xl" />
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center">
              <Swords size={15} className="text-emerald-400" />
            </div>
            <div>
              <h4 className="font-semibold text-slate-200">Combined Red Team</h4>
              <p className="text-xs text-slate-500">All vulnerabilities from both models</p>
            </div>
          </div>
          {combinedResult && (
            <div className="text-xs text-slate-400">
              {combinedResult.summary.successful_attacks} exploits /{' '}
              {combinedResult.summary.total_attacks_simulated} attacks
            </div>
          )}
        </div>
        <button
          onClick={() => runPipeline('combined')}
          disabled={loadingCombined}
          className={`w-full py-2.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all ${loadingCombined
            ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            : 'bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-slate-950 shadow-lg shadow-emerald-500/10'
            }`}
        >
          {loadingCombined ? (
            <>
              <Loader2 size={15} className="animate-spin" />
              Running combined pipeline…
            </>
          ) : (
            <>
              <Swords size={15} />
              Run Full Red Team (Qwen + Mistral)
            </>
          )}
        </button>
        {combinedResult && (
          <div className="grid grid-cols-4 gap-3 mt-4">
            {[
              { label: 'Vulns', value: combinedResult.summary.vulnerabilities_analyzed },
              { label: 'Attacks', value: combinedResult.summary.total_attacks_simulated },
              { label: 'Exploits', value: combinedResult.summary.successful_attacks },
              { label: 'High Risk', value: combinedResult.high_risk_findings.length },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-950/40 rounded-xl p-3 text-center border border-slate-800/50">
                <p className="text-2xl font-bold text-emerald-400">{value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Unified exploits table */}
      {allFindings.length > 0 && (
        <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl">
          <h4 className="text-base font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-400" />
            All Successful Exploits
            <span className="text-xs font-normal text-slate-500 bg-red-500/10 border border-red-500/20 text-red-400 px-2 py-0.5 rounded-full ml-1">
              {allFindings.length} total
            </span>
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="text-left pb-2 pr-4 font-medium">Attack</th>
                  <th className="text-left pb-2 pr-4 font-medium">Endpoint</th>
                  <th className="text-left pb-2 pr-4 font-medium">Severity</th>
                  <th className="text-left pb-2 pr-4 font-medium">Difficulty</th>
                  <th className="text-left pb-2 font-medium">Source Model</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {allFindings.map((f, i) => (
                  <tr key={i} className="hover:bg-slate-800/20 transition-colors">
                    <td className="py-2.5 pr-4 font-medium text-slate-200">{f.attack_name}</td>
                    <td className="py-2.5 pr-4 font-mono text-slate-400">
                      <span className="text-slate-500 mr-1">{f.target_method}</span>
                      {f.target_endpoint}
                    </td>
                    <td className="py-2.5 pr-4">
                      <span className={`px-2 py-0.5 rounded-full border ${severityClass(f.original_severity)}`}>
                        {f.original_severity}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-slate-400">{f.exploitation_difficulty}</td>
                    <td className="py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded-full border text-xs font-semibold ${f._model === 'qwen'
                          ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                          : f._model === 'mistral'
                            ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          }`}
                      >
                        {f._model.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState({ score: 100, drift: 0, exploits_prevented: 0 });
  const [recentScans, setRecentScans] = useState<any[]>([]);

  const [isConfigured, setIsConfigured] = useState(() => {
    return localStorage.getItem('sentinel_configured') === 'true';
  });
  const [repoUrl, setRepoUrl] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [aiStatus, setAiStatus] = useState({ mistral: 'checking', qwen: 'checking' });
  const [scanProgress, setScanProgress] = useState(0);
  const [, setPrevScanCount] = useState(-1);
  const [selectedScan, setSelectedScan] = useState<any>(null);
  const scanBaselineRef = useRef<number>(0);

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
    fetch('/api/dashboard/vulnerabilities').then(r => r.json()).then(d => { if (Array.isArray(d)) { } }).catch(() => { });
  };

  const clearHistory = () => {
    if (!confirm('Clear all scan history? This cannot be undone.')) return;
    fetch('/api/dashboard/reset', { method: 'POST' })
      .then(() => {
        setStats({ score: 100, drift: 0, exploits_prevented: 0 });
        setRecentScans([]);
        setScanProgress(0);
        localStorage.removeItem('sentinel_configured');
        setIsConfigured(false);
      })
      .catch(() => {
        setStats({ score: 100, drift: 0, exploits_prevented: 0 });
        setRecentScans([]);
        setScanProgress(0);
        localStorage.removeItem('sentinel_configured');
        setIsConfigured(false);
      });
  };

  useEffect(() => {
    if (!isScanning) return;
    setScanProgress(2);
    const tick = setInterval(() => {
      setScanProgress(p => Math.min(98, p + (100 / 90) * 3));
      fetch('/api/dashboard/recent_scans')
        .then(r => r.json())
        .then((d: any[]) => {
          if (!Array.isArray(d)) return;
          if (d.length > scanBaselineRef.current) {
            clearInterval(tick);
            setIsScanning(false);
            setScanProgress(0);
            setRecentScans(d);
            fetchDashboard();
          }
        })
        .catch(() => { });
    }, 3000);
    return () => clearInterval(tick);
  }, [isScanning]);

  useEffect(() => {
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
            scanBaselineRef.current = recentScans.length;
            fetch('/api/scan', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ github_url: repoUrl })
            }).then(() => {
              setIsConfigured(true);
              localStorage.setItem('sentinel_configured', 'true');
            }).catch(() => {
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
            onClick={() => setActiveTab('pr')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'pr' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
          >
            <GitBranch size={18} />
            PR Scans
          </button>
          <button
            onClick={() => setActiveTab('redteam')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'redteam' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}
          >
            <Swords size={18} />
            Red Team
            <span className="ml-auto text-xs px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-semibold">
              NEW
            </span>
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
          <h2 className="text-xl font-medium text-slate-200 capitalize flex items-center gap-2">
            {activeTab === 'redteam' && <Swords size={18} className="text-red-400" />}
            {activeTab === 'redteam' ? 'Red Team' : activeTab.replace('_', ' ')}
          </h2>
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

        {/* ── Red Team Tab ── */}
        {activeTab === 'redteam' && (
          <main className="flex-1 p-8 z-10 w-full max-w-7xl mx-auto">
            <RedTeamPanel aiStatus={aiStatus} />
          </main>
        )}

        {/* ── Overview Tab ── */}
        {activeTab === 'overview' && (
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

            {/* Graph Visualization */}
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md shadow-xl h-96 flex flex-col relative overflow-hidden group">
              <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-emerald-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-duration-500"></div>
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h3 className="text-lg font-medium text-slate-200">Authorization Graph</h3>
                  <p className="text-sm text-slate-500">Role &rarr; Route &rarr; Resource Mapping</p>
                </div>
              </div>
              <div className="flex-1 border border-slate-800/50 rounded-xl bg-slate-950/50 flex items-center justify-center relative overflow-hidden">
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
          </main>
        )}

        {/* ── PR Scans Tab ── */}
        {activeTab === 'pr' && (
          <main className="flex-1 p-8 z-10 w-full max-w-7xl mx-auto space-y-6">
            <div>
              <h3 className="text-xl font-semibold text-slate-200">PR Scan History</h3>
              <p className="text-sm text-slate-500 mt-1">All repository scans with AI security analysis results</p>
            </div>
            {recentScans.length === 0 ? (
              <div className="text-center py-20 text-slate-500">
                <GitBranch size={40} className="mx-auto mb-4 opacity-30" />
                <p>No scans yet. Submit a repository URL to begin analysis.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {recentScans.map((pr, i) => {
                  const vulns: any[] = (() => {
                    try { return Array.isArray(pr.vulnerabilities) ? pr.vulnerabilities : JSON.parse(pr.vulnerabilities || '[]'); }
                    catch { return []; }
                  })();
                  const byType: Record<string, number> = {};
                  vulns.forEach((v: any) => { byType[v.vulnerability_type] = (byType[v.vulnerability_type] || 0) + 1; });
                  return (
                    <div key={i} className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-md hover:border-emerald-500/20 transition-all">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-4">
                          <div className={`mt-1 w-3 h-3 rounded-full flex-shrink-0 ${pr.status === 'Passed' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]'}`} />
                          <div>
                            <p className="font-semibold text-slate-200">{pr.title}</p>
                            <p className="text-xs text-slate-500 mt-0.5">{pr.id} · {pr.time}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${pr.status === 'Passed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30'}`}>{pr.status}</span>
                          {pr.score !== undefined && (
                            <span className="text-sm font-bold text-slate-300">Score: <span className={pr.score >= 80 ? 'text-emerald-400' : 'text-red-400'}>{pr.score}</span></span>
                          )}
                          <button onClick={() => setSelectedScan(pr)} className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm font-medium transition-colors">View Details</button>
                        </div>
                      </div>
                      {vulns.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-slate-800/60 flex flex-wrap gap-2">
                          {Object.entries(byType).map(([type, count]) => (
                            <span key={type} className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${type === 'BOLA' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' : type === 'IDOR' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' : type === 'Privilege Escalation' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>{type} ×{count}</span>
                          ))}
                        </div>
                      )}
                      {vulns.length === 0 && (
                        <div className="mt-4 pt-4 border-t border-slate-800/60"><span className="text-xs text-emerald-500 font-medium">✓ No vulnerabilities detected</span></div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </main>
        )}

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
                        {v.validated_by && (
                          <p className="text-xs text-slate-600 mt-1">
                            Validated by: <span className="text-slate-400">{v.validated_by}</span>
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;

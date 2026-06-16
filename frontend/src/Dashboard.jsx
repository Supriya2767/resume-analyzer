// Dashboard.jsx – Step 2: Display all analysis results + JD matching
//
// Shows:
// - ATS score gauge + breakdown bar chart
// - Extracted resume info (name, email, skills)
// - JD matching (paste a JD, see match %)
// - Improvement suggestions
//
// Uses Recharts for all charts.

import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  RadialBarChart, RadialBar,
} from "recharts";

const API = "https://resume-analyzer-k0ka.onrender.com";

// ── Small Reusable Components ──────────────────────────────────────────────

// Score card tile
function ScoreCard({ label, value, sub, color }) {
  const colors = {
    green:  "text-emerald-400 border-emerald-500/30 bg-emerald-500/5",
    blue:   "text-blue-400   border-blue-500/30   bg-blue-500/5",
    amber:  "text-amber-400  border-amber-500/30  bg-amber-500/5",
  };
  return (
    <div className={`border rounded-xl p-5 ${colors[color]}`}>
      <p className="text-slate-500 text-xs mb-1 font-medium">{label}</p>
      <p className={`text-4xl font-black mb-1 ${colors[color].split(" ")[0]}`}>{value}</p>
      <p className="text-slate-500 text-xs">{sub}</p>
    </div>
  );
}

// Skill pill badge
function Badge({ label, variant }) {
  const v = {
    green:  "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    red:    "bg-red-500/15     text-red-400     border-red-500/30",
    slate:  "bg-slate-800      text-slate-300   border-slate-700",
  };
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium border ${v[variant]}`}>
      {label}
    </span>
  );
}

// Returns a hex color string based on numeric score
function scoreColor(s) {
  if (s >= 80) return "#10b981";  // green
  if (s >= 60) return "#3b82f6";  // blue
  if (s >= 40) return "#f59e0b";  // amber
  return "#ef4444";               // red
}


// ── Main Dashboard Component ───────────────────────────────────────────────

export default function Dashboard({ resumeData, atsResult, matchResult, rawText, onMatch }) {

  const [jdText, setJdText]     = useState("");
  const [jdLoading, setJdLoading] = useState(false);
  const [jdError, setJdError]   = useState("");

  const ats    = atsResult   || {};
  const parsed = resumeData  || {};
  const match  = matchResult || {};

  // ── JD Match API call ──────────────────────────────────────────
  async function handleMatch() {
    if (!jdText.trim()) { setJdError("Please paste a job description."); return; }
    if (!rawText)       { setJdError("Upload a resume first."); return; }

    setJdLoading(true);
    setJdError("");

    try {
      const res = await fetch(`${API}/match-job-description`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_text: rawText, job_description: jdText }),
      });
      if (!res.ok) throw new Error("Matching failed.");
      const data = await res.json();
      onMatch(data.match_result);   // Lift result up to App.jsx
    } catch (e) {
      setJdError(e.message);
    } finally {
      setJdLoading(false);
    }
  }

  // ── Chart Data ─────────────────────────────────────────────────

  // Bar chart: ATS score component breakdown
  const breakdownData = [
    { name: "Keywords",     score: ats.breakdown?.keyword_score     || 0 },
    { name: "Skills",       score: ats.breakdown?.skills_score      || 0 },
    { name: "Completeness", score: ats.breakdown?.completeness_score || 0 },
  ];

  // Pie chart: matched vs missing JD keywords
  const pieData = matchResult
    ? [
        { name: "Matched", value: match.total_matched || 0 },
        { name: "Missing", value: (match.total_jd_keywords || 0) - (match.total_matched || 0) },
      ]
    : [];

  // ── Early return if no data ────────────────────────────────────
  if (!resumeData && !atsResult) {
    return (
      <div className="text-center py-28">
        <p className="text-5xl mb-5">📊</p>
        <h2 className="text-2xl font-bold text-white mb-3">No Data Yet</h2>
        <p className="text-slate-400">Go to Step 01 to upload your resume first.</p>
      </div>
    );
  }

  // ── Full Dashboard ─────────────────────────────────────────────
  return (
    <div className="space-y-8">

      {/* Page header */}
      <div>
        <p className="text-emerald-400 text-xs tracking-widest mb-1">STEP 02</p>
        <h1 className="text-3xl font-bold text-white">Analysis Dashboard</h1>
        {parsed.name && (
          <p className="text-slate-400 mt-1">
            Results for: <span className="text-emerald-400">{parsed.name}</span>
          </p>
        )}
      </div>

      {/* ── SCORE CARDS ───────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        <ScoreCard
          label="ATS Score"
          value={`${ats.ats_score ?? "—"}%`}
          sub={ats.rating || ""}
          color="green"
        />
        <ScoreCard
          label="JD Match"
          value={matchResult ? `${match.match_percentage}%` : "—"}
          sub={match.match_quality || "Paste a JD below"}
          color="blue"
        />
        <ScoreCard
          label="Skills Found"
          value={parsed.skills?.length ?? "—"}
          sub="unique skills detected"
          color="amber"
        />
      </div>

      {/* ── ATS CHARTS ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-6">

        {/* Radial gauge — overall ATS score */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4">ATS Score Gauge</h3>
          <ResponsiveContainer width="100%" height={180}>
            <RadialBarChart
              cx="50%" cy="75%"
              innerRadius="60%" outerRadius="90%"
              startAngle={180} endAngle={0}
              data={[{ value: ats.ats_score || 0, fill: scoreColor(ats.ats_score) }]}
            >
              <RadialBar dataKey="value" cornerRadius={8} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="text-center -mt-4">
            <span className="text-4xl font-black" style={{ color: scoreColor(ats.ats_score) }}>
              {ats.ats_score ?? 0}
            </span>
            <span className="text-slate-400"> / 100</span>
            <p className="text-slate-500 text-sm">{ats.rating}</p>
          </div>
        </div>

        {/* Bar chart — score component breakdown */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4">Score Breakdown</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={breakdownData} barSize={30}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                labelStyle={{ color: "#e2e8f0" }}
              />
              <Bar dataKey="score" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── JD MATCH SECTION ──────────────────────────────────────── */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-1">Job Description Matching</h3>
        <p className="text-slate-500 text-sm mb-4">
          Paste a job description to see how well your resume matches it.
        </p>

        <textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="Paste the full job description here…"
          rows={7}
          className="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 text-slate-300 text-sm resize-none focus:outline-none focus:border-emerald-500"
        />

        {jdError && (
          <p className="text-red-400 text-sm mt-2">⚠ {jdError}</p>
        )}

        <button
          onClick={handleMatch}
          disabled={!jdText.trim() || jdLoading}
          className={`mt-3 px-6 py-3 rounded-lg font-semibold text-sm transition-all ${
            !jdText.trim() || jdLoading
              ? "bg-slate-700 text-slate-500 cursor-not-allowed"
              : "bg-emerald-500 text-slate-950 hover:bg-emerald-400 active:scale-95"
          }`}
        >
          {jdLoading ? "⚙ Matching…" : "Match Against Resume →"}
        </button>

        {/* JD match results */}
        {matchResult && (
          <div className="mt-6 grid grid-cols-2 gap-6">

            {/* Pie chart */}
            <div>
              <p className="text-slate-400 text-sm font-medium mb-3">Keyword Coverage</p>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={70} label>
                    <Cell fill="#10b981" />
                    <Cell fill="#ef4444" />
                  </Pie>
                  <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Missing keywords */}
            <div>
              <p className="text-slate-400 text-sm font-medium mb-3">
                Missing Keywords <span className="text-slate-600">(add these to improve match)</span>
              </p>
              <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
                {(match.missing_skills || []).slice(0, 16).map((kw) => (
                  <Badge key={kw} label={kw} variant="red" />
                ))}
                {!match.missing_skills?.length && (
                  <p className="text-emerald-400 text-sm">🎉 No critical gaps found!</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── RESUME INFO + SKILLS ──────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-6">

        {/* Extracted info */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4">Extracted Info</h3>
          <div className="space-y-3 text-sm">
            {[
              { k: "Name",  v: parsed.name  },
              { k: "Email", v: parsed.email },
              { k: "Phone", v: parsed.phone },
            ].map(({ k, v }) => (
              <div key={k} className="flex gap-3">
                <span className="text-slate-500 w-14 shrink-0">{k}</span>
                <span className="text-slate-300 break-all">
                  {v || <span className="text-red-400 text-xs">Not found</span>}
                </span>
              </div>
            ))}

            {parsed.education?.length > 0 && (
              <div>
                <p className="text-slate-500 mb-1">Education</p>
                {parsed.education.slice(0, 2).map((e, i) => (
                  <p key={i} className="text-slate-300 text-xs pl-3 border-l border-slate-700 mb-1">{e}</p>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Skills found */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-4">
            Skills Detected
            <span className="text-emerald-400 ml-2 text-sm font-normal">
              ({parsed.skills?.length || 0})
            </span>
          </h3>
          <div className="flex flex-wrap gap-2 max-h-52 overflow-y-auto">
            {(parsed.skills || []).map((s) => (
              <Badge key={s} label={s} variant="green" />
            ))}
            {!parsed.skills?.length && (
              <p className="text-slate-500 text-sm">No skills detected.</p>
            )}
          </div>
        </div>
      </div>

      {/* ── SUGGESTIONS ───────────────────────────────────────────── */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">💡 Improvement Suggestions</h3>
        <div className="space-y-3">
          {[
            ...(ats.suggestions || []),
            ...(match.recommendations || []),
          ]
            .filter((v, i, a) => a.indexOf(v) === i)  // deduplicate
            .slice(0, 10)
            .map((tip, i) => (
              <div key={i} className="flex gap-3 p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg">
                <span className="text-emerald-500 font-bold text-xs w-5 h-5 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <p className="text-slate-300 text-sm">{tip}</p>
              </div>
            ))}
        </div>
      </div>

    </div>
  );
}
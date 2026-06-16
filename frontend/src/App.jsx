// App.jsx – Root component that manages page navigation and shared state.
//
// We use React's useState instead of React Router to keep things simple.
// All shared data (resume, ATS score, JD match) lives here and is passed
// down to child pages via props. This is called "lifting state up".

import { useState } from "react";
import UploadResume from "./UploadResume.jsx";
import Dashboard from "./Dashboard.jsx";

export default function App() {
  // Which page to show: "upload" or "dashboard"
  const [page, setPage] = useState("upload");

  // All analysis data lives here so both pages can access it
  const [resumeData, setResumeData]   = useState(null);  // Parsed name/email/skills
  const [atsResult, setAtsResult]     = useState(null);  // ATS score + breakdown
  const [matchResult, setMatchResult] = useState(null);  // JD match result
  const [rawText, setRawText]         = useState("");    // Raw resume text

  // Called by UploadResume when analysis is complete
  function handleAnalysisDone(data) {
    setResumeData(data.parsed_data);
    setRawText(data.raw_text);
    setAtsResult(data.ats_result);
    setPage("dashboard");
  }

  // Called by Dashboard when JD matching is complete
  function handleMatchDone(result) {
    setMatchResult(result);
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-mono">

      {/* ── Navigation Bar ─────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur border-b border-slate-800">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">

          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-emerald-500 flex items-center justify-center">
              <span className="text-slate-950 font-black text-sm">R</span>
            </div>
            <span className="text-emerald-400 font-bold tracking-widest text-lg">
              ResumeAI
            </span>
          </div>

          {/* Nav links */}
          <div className="flex gap-2">
            {[
              { id: "upload",    label: "01 · Upload"    },
              { id: "dashboard", label: "02 · Dashboard" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                className={`px-4 py-2 rounded text-sm font-medium transition-all ${
                  page === item.id
                    ? "bg-emerald-500 text-slate-950"
                    : "text-slate-400 hover:text-emerald-400 hover:bg-slate-800"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* ── Page Content ────────────────────────────────────────── */}
      <main className="max-w-5xl mx-auto px-6 py-10">
        {page === "upload" && (
          <UploadResume onDone={handleAnalysisDone} />
        )}
        {page === "dashboard" && (
          <Dashboard
            resumeData={resumeData}
            atsResult={atsResult}
            matchResult={matchResult}
            rawText={rawText}
            onMatch={handleMatchDone}
          />
        )}
      </main>
    </div>
  );
}
// UploadResume.jsx – Step 1: PDF upload + ATS analysis
//
// What this page does:
// 1. Let user pick a PDF (drag-and-drop or file picker)
// 2. POST to /upload-resume  → extract + parse resume
// 3. POST to /analyze-resume → calculate ATS score
// 4. Pass all results up to App.jsx via the onDone() prop

import { useState, useRef } from "react";

const API = "https://resume-analyzer-k0ka.onrender.com";

export default function UploadResume({ onDone }) {
  const [file, setFile]         = useState(null);    // Selected PDF
  const [loading, setLoading]   = useState(false);   // Show spinner
  const [error, setError]       = useState("");       // Error message
  const [dragOver, setDragOver] = useState(false);   // Drag-over highlight
  const inputRef                = useRef(null);       // Hidden <input type="file">

  // Validate and store the selected file
  function selectFile(f) {
    if (f && f.type === "application/pdf") {
      setFile(f);
      setError("");
    } else {
      setError("Please choose a PDF file.");
    }
  }

  // Drag-and-drop handlers
  function onDragOver(e)  { e.preventDefault(); setDragOver(true);  }
  function onDragLeave()  { setDragOver(false); }
  function onDrop(e)      { e.preventDefault(); setDragOver(false); selectFile(e.dataTransfer.files[0]); }

  // Main upload + analysis flow
  async function handleSubmit() {
    if (!file) { setError("Please select a PDF first."); return; }

    setLoading(true);
    setError("");

    try {
      // ── STEP 1: Upload PDF ──────────────────────────────────────
      // FormData is the browser API for sending files via HTTP
      const form = new FormData();
      form.append("file", file);   // "file" must match the FastAPI param name

      const uploadRes = await fetch(`${API}/upload-resume`, {
        method: "POST",
        body: form,
        // ⚠️ Do NOT set Content-Type here.
        // The browser sets it automatically with the correct boundary.
      });

      if (!uploadRes.ok) {
        const err = await uploadRes.json();
        throw new Error(err.detail || "Upload failed.");
      }

      const uploadData = await uploadRes.json();

      // ── STEP 2: Calculate ATS Score ─────────────────────────────
      const atsRes = await fetch(`${API}/analyze-resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_text: uploadData.raw_text,
          filename: uploadData.filename,
        }),
      });

      if (!atsRes.ok) throw new Error("ATS analysis failed.");
      const atsData = await atsRes.json();

      // ── Pass everything up to App.jsx ───────────────────────────
      onDone({
        parsed_data: uploadData.parsed_data,
        raw_text:    uploadData.raw_text,
        ats_result:  atsData.ats_result,
        filename:    uploadData.filename,
      });

    } catch (err) {
      setError(err.message || "Something went wrong. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto">

      {/* ── Page Header ──────────────────────────────────────────── */}
      <p className="text-emerald-400 text-xs tracking-widest mb-2">STEP 01</p>
      <h1 className="text-3xl font-bold text-white mb-2">Upload Your Resume</h1>
      <p className="text-slate-400 mb-8">
        Upload a PDF resume to extract skills, score it against ATS criteria,
        and get improvement suggestions.
      </p>

      {/* ── Drop Zone ────────────────────────────────────────────── */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`
          cursor-pointer border-2 border-dashed rounded-xl p-14 text-center
          transition-all select-none
          ${dragOver
            ? "border-emerald-400 bg-emerald-500/10"
            : file
              ? "border-emerald-500 bg-emerald-500/5"
              : "border-slate-600 bg-slate-900 hover:border-slate-500"
          }
        `}
      >
        {/* Hidden native file input */}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => selectFile(e.target.files[0])}
        />

        <div className="text-5xl mb-3">{file ? "✅" : "📄"}</div>

        {file ? (
          <>
            <p className="text-emerald-400 font-semibold">{file.name}</p>
            <p className="text-slate-500 text-sm mt-1">
              {(file.size / 1024).toFixed(1)} KB · Click to replace
            </p>
          </>
        ) : (
          <>
            <p className="text-slate-300 font-semibold text-lg mb-1">
              Drop your PDF here
            </p>
            <p className="text-slate-500 text-sm">or click to browse</p>
          </>
        )}
      </div>

      {/* ── Error Message ────────────────────────────────────────── */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          ⚠ {error}
        </div>
      )}

      {/* ── Submit Button ─────────────────────────────────────────── */}
      <button
        onClick={handleSubmit}
        disabled={!file || loading}
        className={`
          mt-5 w-full py-4 rounded-xl font-bold text-lg transition-all
          ${!file || loading
            ? "bg-slate-700 text-slate-500 cursor-not-allowed"
            : "bg-emerald-500 text-slate-950 hover:bg-emerald-400 active:scale-95"
          }
        `}
      >
        {loading
          ? "⚙  Analyzing Resume…"
          : "Analyze Resume →"
        }
      </button>

      {/* ── Info Cards ───────────────────────────────────────────── */}
      <div className="mt-8 grid grid-cols-3 gap-3">
        {[
          { icon: "🔍", title: "NLP Parsing",  desc: "spaCy extracts name, skills, education" },
          { icon: "📊", title: "ATS Score",    desc: "Weighted score like real ATS software" },
          { icon: "💡", title: "Suggestions",  desc: "Actionable tips to improve your resume" },
        ].map((c) => (
          <div key={c.title} className="bg-slate-900 border border-slate-800 rounded-lg p-4 text-center">
            <div className="text-2xl mb-1">{c.icon}</div>
            <div className="text-white text-xs font-semibold">{c.title}</div>
            <div className="text-slate-500 text-xs mt-1">{c.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
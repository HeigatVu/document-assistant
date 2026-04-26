"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { FileText, Send, Loader2, CheckCircle2, Sparkles } from "lucide-react";

const API_BASE = "http://localhost:8000/api";

export default function Dashboard() {
  const [documents, setDocuments] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const res = await axios.get(`${API_BASE}/documents`);
      setDocuments(res.data.documents);
    } catch (err) {
      console.error("Failed to fetch documents", err);
    }
  };

  const submitTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    
    setLoading(true);
    setError("");
    setResult(null);
    
    try {
      const res = await axios.post(`${API_BASE}/task`, {
        prompt,
        reading_model: "gemini-1.5-pro",
        writing_model: "gemini-1.5-flash",
      });
      setResult(res.data);
      fetchDocuments(); // refresh list
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30">
      {/* Background gradients */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px]" />
      </div>

      <main className="relative z-10 max-w-7xl mx-auto p-6 lg:p-12 flex flex-col h-screen">
        <header className="mb-8 flex items-center gap-3">
          <div className="p-3 bg-indigo-500/10 rounded-2xl ring-1 ring-indigo-500/20">
            <Sparkles className="w-6 h-6 text-indigo-400" />
          </div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400">
            Wiki Assistant
          </h1>
        </header>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-8 min-h-0">
          {/* Sidebar: Documents */}
          <section className="flex flex-col gap-4 bg-slate-900/50 backdrop-blur-xl rounded-3xl border border-slate-800 p-6 shadow-2xl overflow-hidden">
            <h2 className="text-lg font-semibold flex items-center gap-2 text-slate-300">
              <FileText className="w-5 h-5 text-purple-400" />
              Ingested Documents
            </h2>
            <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
              {documents.length === 0 ? (
                <p className="text-slate-500 text-sm p-4 text-center border border-dashed border-slate-800 rounded-xl">
                  No documents found
                </p>
              ) : (
                documents.map((doc, i) => (
                  <div key={i} className="group p-3 rounded-xl bg-slate-800/40 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-500/30 transition-all cursor-default">
                    <p className="text-sm font-medium truncate">{doc}</p>
                  </div>
                ))
              )}
            </div>
          </section>

          {/* Main Task Area */}
          <section className="lg:col-span-2 flex flex-col gap-4">
            {/* Task Result / History */}
            <div className="flex-1 bg-slate-900/50 backdrop-blur-xl rounded-3xl border border-slate-800 p-6 shadow-2xl overflow-y-auto flex flex-col justify-end">
              {error && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-2xl mb-4 animate-in fade-in slide-in-from-bottom-4">
                  <p className="font-medium">Error</p>
                  <p className="text-sm opacity-80">{error}</p>
                </div>
              )}
              
              {result && (
                <div className="bg-indigo-500/10 border border-indigo-500/20 p-5 rounded-2xl animate-in fade-in slide-in-from-bottom-4">
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle2 className="w-5 h-5 text-indigo-400" />
                    <h3 className="font-semibold text-indigo-100">Task Completed</h3>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed mb-4">{result.summary}</p>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800">
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Output File</p>
                      <p className="text-sm truncate text-indigo-300 font-medium">{result.output_file}</p>
                    </div>
                    <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800">
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">References Used</p>
                      <p className="text-sm truncate text-slate-300">{result.referenced_files?.join(", ") || "None"}</p>
                    </div>
                  </div>
                </div>
              )}
              
              {!result && !error && !loading && (
                <div className="text-center p-8 m-auto max-w-sm">
                  <div className="w-16 h-16 mx-auto bg-slate-800/50 rounded-2xl flex items-center justify-center mb-4 border border-slate-800 shadow-inner">
                    <Sparkles className="w-8 h-8 text-slate-500" />
                  </div>
                  <h3 className="text-lg font-medium text-slate-300 mb-2">How can I help?</h3>
                  <p className="text-sm text-slate-500">Ask me to synthesize documents, draft a new report, or edit an existing file.</p>
                </div>
              )}
            </div>

            {/* Input Form */}
            <form onSubmit={submitTask} className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-[2rem] blur opacity-20 group-hover:opacity-40 transition duration-500" />
              <div className="relative flex items-center bg-slate-900 border border-slate-800 rounded-3xl p-2 shadow-xl focus-within:ring-2 focus-within:ring-indigo-500/50 transition-all">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g. Generate a summary of our finance documents..."
                  className="flex-1 bg-transparent border-none focus:outline-none px-4 py-3 text-slate-200 placeholder:text-slate-600 text-[15px]"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !prompt.trim()}
                  className="p-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-2xl transition-colors shrink-0 flex items-center justify-center min-w-[48px]"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </button>
              </div>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}

"use client";

import { useState, useEffect, useRef } from "react";
import { FileText, Send, Loader2, CheckCircle2, Sparkles, Upload, Clock, X, Terminal, ExternalLink, FolderOpen, Trash2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const TYPE_HINTS: Record<string, string> = {
  CV: "Curriculum Vitae",
  PRO: "Proposals",
  CON: "Contracts & Agreements",
  ETH: "Ethics & IRB",
  BUD: "Budgets & Finance",
  REQ: "Request Letters",
  ADM: "Admin & LoS",
  REP: "Reports",
  SCH: "Schedules & Plans",
  PRE: "Presentations",
  CRF: "Case Report Forms",
  FIG: "Figures & Images",
  GDL: "Guidelines",
  COR: "Correspondence",
};

export default function Dashboard() {
  const [documents, setDocuments] = useState<{name: string, status: string}[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [readingModel, setReadingModel] = useState("gemini-3-flash-preview");
  const [writingModel, setWritingModel] = useState("gemini-3.1-flash-lite-preview");
  const [templateFile, setTemplateFile] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [useCli, setUseCli] = useState(false);
  const [processLogs, setProcessLogs] = useState<{step: string, details: string}[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    fetchDocuments();
    fetchHistory();
    fetchTypes();
  }, []);

  const fetchTypes = async () => {
    try {
      const res = await fetch(`${API_BASE}/types`);
      const data = await res.json();
      setTypes(data.types || []);
    } catch (err) {
      console.error("Failed to fetch types", err);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/history`);
      const data = await res.json();
      setHistory(data.history || []);
    } catch (err) {
      console.error("Failed to fetch history", err);
    }
  };
  
  const ingestDocument = async (filename: string) => {
    setIngesting(filename);
    try {
      const res = await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
      });
      if (!res.ok) throw new Error("Ingestion failed");
      await fetchDocuments();
      await fetchTypes();
    } catch (err: any) {
      setError(err.message || "Ingestion failed");
    } finally {
      setIngesting(null);
    }
  };

  const openDocument = async (filename: string) => {
    try {
      await fetch(`${API_BASE}/open`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
      });
    } catch (err: any) {
      console.error("Failed to open document", err);
    }
  };

  const openOutputFile = async (filename: string) => {
    try {
      await fetch(`${API_BASE}/open_output`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
      });
    } catch (err: any) {
      console.error("Failed to open output document", err);
    }
  };

  const openRawDir = async () => {
    try {
      await fetch(`${API_BASE}/open_dir`, { method: "POST" });
    } catch (err: any) {
      console.error("Failed to open directory", err);
    }
  };

  const openOutputFolder = async (filename: string) => {
    try {
      await fetch(`${API_BASE}/open_output_folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
      });
    } catch (err: any) {
      console.error("Failed to open output folder", err);
    }
  };

  const deleteTask = async (id: number, filename: string) => {
    if (!confirm("Are you sure you want to delete this output file and history entry?")) return;
    try {
      await fetch(`${API_BASE}/delete_task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, filename }),
      });
      await fetchHistory();
    } catch (err: any) {
      console.error("Failed to delete task", err);
    }
  };

  const handleUploadTemplate = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const uploadRes = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });
      const uploadData = await uploadRes.json();
      const filename = uploadData.filename;
      
      await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
      });
      
      setTemplateFile(filename);
      await fetchDocuments();
      await fetchTypes();
    } catch (err: any) {
      setError(err.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`);
      const data = await res.json();
      setDocuments(data.documents || []);
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
    setProcessLogs([]);
    
    try {
      const response = await fetch(`${API_BASE}/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          reading_model: readingModel,
          writing_model: writingModel,
          template_file: templateFile || null,
          type_filter: selectedType || null,
          use_cli: useCli,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Task failed");
      }

      if (useCli && response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              try {
                const parsed = JSON.parse(data);
                if (parsed.type === "skill_update") {
                  setProcessLogs((prev) => [...prev, { step: parsed.step, details: parsed.details }]);
                } else if (parsed.id) {
                  // This is the final history entry
                  setResult(parsed);
                }
              } catch (e) {
                // Not JSON, maybe a status message
                console.log("Stream update:", data);
              }
            }
          }
        }
      } else {
        const data = await response.json();
        setResult(data);
      }
      
      fetchDocuments(); // refresh list
      fetchHistory();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleUploadTemplate}
        className="hidden"
        accept=".pdf,.docx"
      />
      {/* Background gradients */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px]" />
      </div>

      <main className="relative z-10 max-w-7xl mx-auto p-6 lg:p-12 flex flex-col h-screen overflow-hidden">
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
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold flex items-center gap-2 text-slate-300">
                <FileText className="w-5 h-5 text-purple-400" />
                Document Library
              </h2>
              <button 
                onClick={openRawDir} 
                className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-indigo-400 transition-colors" 
                title="Open source folder"
              >
                <FolderOpen className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
              {documents.length === 0 ? (
                <p className="text-slate-500 text-sm p-4 text-center border border-dashed border-slate-800 rounded-xl">
                  No documents found
                </p>
              ) : (
                documents.map((doc, i) => (
                  <div key={i} className="group p-3 rounded-xl bg-slate-800/40 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-500/30 transition-all flex items-center justify-between gap-3">
                    <div 
                      className="flex-1 min-w-0 cursor-pointer" 
                      onClick={() => openDocument(doc.name)}
                      title="Open source file"
                    >
                      <p className="text-sm font-medium truncate text-slate-200 group-hover:text-indigo-400 transition-colors flex items-center gap-2">
                        {doc.name}
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`w-1.5 h-1.5 rounded-full ${doc.status === 'ingested' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                        <span className={`text-[10px] uppercase tracking-widest font-bold ${doc.status === 'ingested' ? 'text-emerald-400/80' : 'text-amber-400/80'}`}>
                          {doc.status}
                        </span>
                      </div>
                    </div>
                    
                    {doc.status === 'pending' && (
                      <button 
                        onClick={() => ingestDocument(doc.name)}
                        disabled={ingesting === doc.name}
                        title="Ingest document"
                        className="p-2 bg-indigo-500/10 hover:bg-indigo-500/30 text-indigo-400 rounded-xl transition-all border border-indigo-500/20 hover:border-indigo-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {ingesting === doc.name ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Sparkles className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>


          {/* Main Task Area */}
          <section className="lg:col-span-2 flex flex-col gap-4 min-h-0">
            {/* Task Result / History */}
            <div className="flex-1 bg-slate-900/50 backdrop-blur-xl rounded-3xl border border-slate-800 p-6 shadow-2xl overflow-y-auto flex flex-col">
              
              {/* History List */}
              {history.length > 0 && !result && selectedType === null && (
                <div className="space-y-3 mb-10 pb-10 border-b border-slate-800/50 pr-2">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2 sticky top-[-24px] bg-slate-900/90 backdrop-blur-md py-3 z-10 rounded-t-xl">
                    <Clock className="w-3 h-3" />
                    Recent Activity
                  </h3>
                  {history.map((item, idx) => (
                    <div key={idx} className="p-4 rounded-2xl bg-slate-800/20 border border-slate-800/50 hover:border-indigo-500/20 transition-all group">
                      <div className="flex justify-between items-start mb-2">
                        <p className="text-xs font-medium text-slate-400 line-clamp-1 flex-1 pr-4 italic">
                          "{item.prompt}"
                        </p>
                        <span className="text-[10px] text-slate-600 font-mono whitespace-nowrap">
                          {item.created_at}
                        </span>
                      </div>
                      <p className="text-sm text-slate-300 line-clamp-2 mb-3 leading-relaxed">
                        {item.summary}
                      </p>
                      <div className="flex justify-between items-center mt-3">
                        <div 
                          className="flex items-center gap-2 text-[10px] font-medium text-indigo-400/70 w-fit cursor-pointer hover:text-indigo-300 transition-colors"
                          onClick={() => openOutputFile(item.output_file)}
                          title="Open generated file"
                        >
                          <FileText className="w-3 h-3" />
                          {item.output_file}
                        </div>
                        <div className="flex items-center gap-1">
                          <button 
                            onClick={() => openOutputFolder(item.output_file)}
                            className="p-1.5 hover:bg-indigo-500/10 rounded-lg text-slate-500 hover:text-indigo-400 transition-all"
                            title="Open folder containing this file"
                          >
                            <FolderOpen className="w-3.5 h-3.5" />
                          </button>
                          <button 
                            onClick={() => deleteTask(item.id, item.output_file)}
                            className="p-1.5 hover:bg-red-500/10 rounded-lg text-slate-500 hover:text-red-400 transition-all"
                            title="Delete file and history"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              
              {result && (
                <div className="bg-indigo-500/10 border border-indigo-500/20 p-5 rounded-2xl animate-in fade-in slide-in-from-bottom-4">
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-indigo-400" />
                      <h3 className="font-semibold text-indigo-100">Task Completed</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      <button 
                        onClick={() => openOutputFolder(result.output_file)}
                        className="p-2 hover:bg-indigo-500/20 rounded-xl text-indigo-400 transition-all border border-indigo-500/20"
                        title="Open folder"
                      >
                        <FolderOpen className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => { deleteTask(result.id, result.output_file); setResult(null); }}
                        className="p-2 hover:bg-red-500/20 rounded-xl text-red-400 transition-all border border-red-500/20"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed mb-4">{result.summary}</p>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800">
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Output File</p>
                      <p 
                        className="text-sm truncate text-indigo-300 font-medium cursor-pointer hover:text-indigo-200 transition-colors flex items-center gap-1 w-fit"
                        onClick={() => openOutputFile(result.output_file)}
                        title="Open generated file"
                      >
                        {result.output_file}
                        <ExternalLink className="w-3 h-3" />
                      </p>
                    </div>
                    <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800">
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">References Used</p>
                      <p className="text-sm truncate text-slate-300">{result.referenced_files?.join(", ") || "None"}</p>
                    </div>
                  </div>
                  <button onClick={() => setResult(null)} className="mt-4 text-xs font-medium text-indigo-400 hover:text-indigo-300">
                    &larr; Start New Task
                  </button>
                </div>
              )}
              
              {!result && (
                <div className={`flex flex-col items-center p-4 ${history.length > 0 && selectedType === null ? 'pt-8' : 'flex-1 justify-center min-h-[400px]'}`}>
                  {loading ? (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 animate-in fade-in duration-500 w-full">
                      <div className="relative mb-8">
                        <div className="absolute inset-0 bg-indigo-500/20 blur-2xl rounded-full animate-pulse" />
                        <Loader2 className="w-12 h-12 text-indigo-500 animate-spin relative z-10" />
                      </div>
                      
                      {useCli ? (
                        <div className="w-full max-w-md space-y-4">
                          <div className="flex items-center justify-between mb-2">
                            <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-400/80">Expert Process</h3>
                            <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">CLI MODE</span>
                          </div>
                          <div className="bg-slate-950/50 border border-slate-800 rounded-2xl p-4 font-mono text-[11px] h-48 overflow-y-auto custom-scrollbar space-y-2 flex flex-col-reverse">
                            {[...processLogs].reverse().map((log, i) => (
                              <div key={i} className="animate-in slide-in-from-left-2 fade-in duration-300">
                                <span className="text-purple-400 font-bold mr-2">[{log.step}]</span>
                                <span className="text-slate-400 leading-relaxed">{log.details}</span>
                              </div>
                            ))}
                            {processLogs.length === 0 && (
                              <div className="text-slate-600 animate-pulse">Initializing expert skills...</div>
                            )}
                          </div>
                          <p className="text-center text-slate-500 text-xs mt-4">Generating high-fidelity document structure...</p>
                        </div>
                      ) : (
                        <div className="text-center">
                          <h3 className="text-lg font-medium text-slate-300 mb-2">Gemini is writing...</h3>
                          <p className="text-sm text-slate-500">This usually takes 15-30 seconds.</p>
                        </div>
                      )}
                    </div>
                  ) : error ? (
                    <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 text-sm flex items-start gap-3 animate-in shake-1 w-full max-w-md mx-auto">
                      <X className="w-5 h-5 shrink-0" />
                      <div>
                        <h4 className="font-bold mb-1">Task Error</h4>
                        <p>{error}</p>
                        <button onClick={() => setError("")} className="mt-3 text-xs font-medium underline underline-offset-4 opacity-70 hover:opacity-100">Try again</button>
                      </div>
                    </div>
                  ) : selectedType ? (
                    <div className="text-center animate-in fade-in zoom-in-95 duration-300">
                      <div className="inline-flex items-center gap-2 bg-indigo-500/20 text-indigo-300 px-5 py-2.5 rounded-full border border-indigo-500/30 mb-6 shadow-[0_0_20px_rgba(99,102,241,0.1)]">
                        <span className="text-sm font-semibold tracking-wide">Searching in: {selectedType}</span>
                        <button 
                          onClick={() => setSelectedType(null)} 
                          className="hover:text-white transition-colors bg-indigo-500/20 hover:bg-indigo-500/40 p-1 rounded-full"
                          title="Clear filter"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      <h3 className="text-2xl font-medium text-slate-200 mb-2">What kind of {selectedType} do you need?</h3>
                      <p className="text-sm text-slate-500">I will only search within this category to find the best template.</p>
                    </div>
                  ) : (
                    <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
                      <div className="text-center mb-8">
                        <h3 className="text-2xl font-medium text-slate-200">Select a Document Category</h3>
                        <p className="text-sm text-slate-500 mt-2">Filter to a specific type, or just search globally below.</p>
                      </div>
                      {types.length > 0 ? (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                          {types.map((t) => (
                            <button
                              key={t}
                              onClick={() => setSelectedType(t)}
                              className="p-6 rounded-2xl bg-slate-800/40 hover:bg-indigo-500/10 border border-slate-800 hover:border-indigo-500/40 transition-all flex flex-col items-center gap-3 group shadow-lg hover:shadow-indigo-500/10"
                            >
                              <div className="p-3 bg-slate-900 rounded-xl group-hover:bg-indigo-500/20 transition-colors shadow-inner">
                                <FileText className="w-6 h-6 text-slate-400 group-hover:text-indigo-400" />
                              </div>
                              <div className="text-center">
                                <span className="font-bold text-slate-300 group-hover:text-indigo-200 tracking-wide block">{t}</span>
                                <span className="text-[10px] text-slate-500 group-hover:text-slate-400 mt-1 block uppercase tracking-tighter">
                                  {TYPE_HINTS[t] || "Document Type"}
                                </span>
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="p-8 border border-dashed border-slate-800 rounded-3xl text-center">
                          <p className="text-slate-500 text-sm">No categories found.</p>
                          <p className="text-slate-600 text-xs mt-1">Ingest some correctly named documents first.</p>
                        </div>
                      )}
                    </div>
                  )}
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
                  placeholder={selectedType ? `Describe the ${selectedType} you want to create...` : "Search globally or describe what you want to create..."}
                  className="flex-1 bg-transparent border-none focus:outline-none px-4 py-3 text-slate-200 placeholder:text-slate-600 text-[15px]"
                  disabled={loading}
                />
                
                {/* CLI Toggle inside Chat Input */}
                <button
                  type="button"
                  onClick={() => setUseCli(!useCli)}
                  disabled={loading}
                  className={`p-2 mr-2 rounded-xl flex items-center gap-1.5 transition-all text-xs font-bold border ${
                    useCli 
                      ? "bg-indigo-500/20 text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/30" 
                      : "bg-slate-800/50 text-slate-400 border-slate-700/50 hover:bg-slate-800 hover:text-slate-300"
                  }`}
                  title={useCli ? "Using Gemini CLI" : "Using API (Click to use CLI)"}
                >
                  <Terminal className="w-4 h-4" />
                  <span className="hidden sm:inline">CLI</span>
                </button>

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

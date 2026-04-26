"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { FileText, Send, Loader2, CheckCircle2, Sparkles, Upload, Clock } from "lucide-react";

const TEMPLATES = [
  { label: "Summarize", prompt: "Please provide a concise summary of the key points in these documents." },
  { label: "Draft Report", prompt: "Generate a professional report structure based on the available documents, including an executive summary and recommendations." },
  { label: "Action Items", prompt: "Extract all action items, owners, and deadlines mentioned in the documents." },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function Dashboard() {
  const [documents, setDocuments] = useState<{name: string, status: string}[]>([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [readingModel, setReadingModel] = useState("gemini-1.5-pro");
  const [writingModel, setWritingModel] = useState("gemini-1.5-flash");
  const [templateFile, setTemplateFile] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    fetchDocuments();
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API_BASE}/history`);
      setHistory(res.data.history);
    } catch (err) {
      console.error("Failed to fetch history", err);
    }
  };
  const ingestDocument = async (filename: string) => {
    setIngesting(filename);
    try {
      await axios.post(`${API_BASE}/ingest`, { filename });
      await fetchDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Ingestion failed");
    } finally {
      setIngesting(null);
    }
  };

  const handleUploadTemplate = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const uploadRes = await axios.post(`${API_BASE}/upload`, formData);
      const filename = uploadRes.data.filename;
      await axios.post(`${API_BASE}/ingest`, { filename });
      setTemplateFile(filename);
      await fetchDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

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
        reading_model: readingModel,
        writing_model: writingModel,
        template_file: templateFile || null,
      });
      setResult(res.data);
      fetchDocuments(); // refresh list
      fetchHistory();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
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
          {/* Sidebar: Documents */}
          <section className="flex flex-col gap-4 bg-slate-900/50 backdrop-blur-xl rounded-3xl border border-slate-800 p-6 shadow-2xl overflow-hidden">
            <h2 className="text-lg font-semibold flex items-center gap-2 text-slate-300">
              <FileText className="w-5 h-5 text-purple-400" />
              Document Library
            </h2>
            <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
              {documents.length === 0 ? (
                <p className="text-slate-500 text-sm p-4 text-center border border-dashed border-slate-800 rounded-xl">
                  No documents found
                </p>
              ) : (
                documents.map((doc, i) => (
                  <div key={i} className="group p-3 rounded-xl bg-slate-800/40 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-500/30 transition-all flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate text-slate-200">{doc.name}</p>
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
          <section className="lg:col-span-2 flex flex-col gap-4">
            {/* Task Result / History */}
            <div className="flex-1 bg-slate-900/50 backdrop-blur-xl rounded-3xl border border-slate-800 p-6 shadow-2xl overflow-y-auto flex flex-col">
              
              {/* History List */}
              {history.length > 0 && (
                <div className="space-y-3 mb-6 pb-6 border-b border-slate-800/50">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
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
                      <div className="flex items-center gap-2 text-[10px] font-medium text-indigo-400/70">
                        <FileText className="w-3 h-3" />
                        {item.output_file}
                      </div>
                    </div>
                  ))}
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
                  <p className="text-sm text-slate-500">Ask me to synthesize, create a new report, or edit an existing document based on the knowledge I have.</p>
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-4 px-2 mb-2 animate-in fade-in slide-in-from-bottom-2 duration-700">
              <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-1.5 shadow-inner">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Reader</span>
                <select 
                  value={readingModel}
                  onChange={(e) => setReadingModel(e.target.value)}
                  className="bg-transparent text-xs font-medium text-indigo-400 focus:outline-none cursor-pointer hover:text-indigo-300 transition-colors"
                >
                  <option value="gemini-1.5-pro">Gemini Pro (Smart)</option>
                  <option value="gemini-1.5-flash">Gemini Flash (Fast)</option>
                </select>
              </div>

              <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-1.5 shadow-inner">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Writer</span>
                <select 
                  value={writingModel}
                  onChange={(e) => setWritingModel(e.target.value)}
                  className="bg-transparent text-xs font-medium text-purple-400 focus:outline-none cursor-pointer hover:text-purple-300 transition-colors"
                >
                  <option value="gemini-1.5-flash">Gemini Flash (Fast)</option>
                  <option value="gemini-1.5-pro">Gemini Pro (Smart)</option>
                </select>
              </div>
              <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-1.5 shadow-inner">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Style Reference</span>
                <select 
                  value={templateFile}
                  onChange={(e) => setTemplateFile(e.target.value)}
                  className="bg-transparent text-xs font-medium text-emerald-400 focus:outline-none cursor-pointer hover:text-emerald-300 transition-colors max-w-[120px]"
                >
                  <option value="">None</option>
                  {documents.filter(d => d.status === 'ingested').map((doc, idx) => (
                    <option key={idx} value={doc.name}>{doc.name.split('/').pop()}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                  className="p-1 hover:bg-slate-800 text-slate-500 hover:text-emerald-400 rounded-lg transition-all"
                  title="Upload template from laptop"
                >
                  <Upload className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            {/* Input Form */}
            <form onSubmit={submitTask} className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-[2rem] blur opacity-20 group-hover:opacity-40 transition duration-500" />
              <div className="relative flex items-center bg-slate-900 border border-slate-800 rounded-3xl p-2 shadow-xl focus-within:ring-2 focus-within:ring-indigo-500/50 transition-all">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g. Can you describe about what text do you want to build"
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


import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, AlertCircle, Download, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Typos/Utils
function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

interface StudentInfo {
  student_id_full: string;
  student_id_num: string;
  surname: string;
  name: string;
  full_name: string;
  confidence: number;
  file_name: string;
}

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<StudentInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
      setResults([]); // reset results
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      setFiles(Array.from(e.dataTransfer.files));
      setResults([]);
      setError(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const processImages = async () => {
    if (files.length === 0) return;

    setIsProcessing(true);
    setError(null);

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    try {
      const resp = await axios.post<{ results: StudentInfo[] }>(`${API_BASE}/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResults(resp.data.results);
    } catch (err: any) {
      console.error(err);
      setError('Failed to process images. Ensure backend is running.');
    } finally {
      setIsProcessing(false);
    }
  };

  const exportCSV = async () => {
    if (results.length === 0) return;
    try {
      const resp = await axios.post(`${API_BASE}/export/download`, { students: results }, {
        responseType: 'blob'
      });

      // Trigger download
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'attendance_list.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error(err);
      setError('Failed to export CSV.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8 font-sans text-slate-900">
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Header */}
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              Attend Check
            </h1>
            <p className="text-slate-500 mt-1">YomiToku Powered Attendance Tool</p>
          </div>
          <div className="text-sm text-slate-400">
            v1.0.0
          </div>
        </header>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Left Column: Upload & Actions */}
          <div className="lg:col-span-1 space-y-6">

            {/* Upload Area */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "border-2 border-dashed rounded-2xl p-8 transition-all cursor-pointer group",
                "flex flex-col items-center justify-center text-center",
                files.length > 0 ? "border-blue-400 bg-blue-50/50" : "border-slate-300 hover:border-blue-400 hover:bg-slate-50",
              )}
            >
              <input
                type="file"
                multiple
                accept="image/*,.pdf"
                className="hidden"
                ref={fileInputRef}
                onChange={handleFileChange}
              />

              <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Upload size={32} />
              </div>
              <h3 className="font-semibold text-lg mb-1">Upload Images</h3>
              <p className="text-slate-500 text-sm">Drag & Drop or Click to Select</p>

              {files.length > 0 && (
                <div className="mt-4 px-3 py-1 bg-white rounded-full text-blue-600 text-sm font-medium shadow-sm">
                  {files.length} file{files.length > 1 ? 's' : ''} selected
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <button
              onClick={processImages}
              disabled={files.length === 0 || isProcessing}
              className={cn(
                "w-full py-4 rounded-xl flex items-center justify-center gap-2 font-bold text-white transition-all shadow-lg shadow-blue-500/20",
                files.length === 0 || isProcessing
                  ? "bg-slate-400 cursor-not-allowed shadow-none"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:translate-y-[-2px]"
              )}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="animate-spin" /> Processing...
                </>
              ) : (
                <>
                  <FileText /> Start Analysis
                </>
              )}
            </button>

            {error && (
              <div className="bg-red-50 text-red-600 p-4 rounded-xl flex items-start gap-3">
                <AlertCircle className="shrink-0 mt-0.5" size={18} />
                <p className="text-sm">{error}</p>
              </div>
            )}
          </div>

          {/* Right Column: Results */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden min-h-[500px] flex flex-col">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                <h2 className="font-semibold flex items-center gap-2">
                  <CheckCircle size={18} className="text-green-500" />
                  Results
                  <span className="text-slate-400 ml-2 font-normal text-sm">
                    {results.length} students found
                  </span>
                </h2>
                <button
                  onClick={exportCSV}
                  disabled={results.length === 0}
                  className="text-sm flex items-center gap-1.5 bg-white border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium text-slate-700"
                >
                  <Download size={14} /> Export CSV
                </button>
              </div>

              <div className="flex-1 overflow-auto">
                {results.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-slate-400">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                      <FileText size={32} className="opacity-20" />
                    </div>
                    <p>No results yet.</p>
                  </div>
                ) : (
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-100 sticky top-0">
                      <tr>
                        <th className="px-4 py-3">ID (Num)</th>
                        <th className="px-4 py-3">Surname</th>
                        <th className="px-4 py-3">Name</th>
                        <th className="px-4 py-3">Full Name</th>
                        <th className="px-4 py-3 text-right">Conf.</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {results.map((student, i) => (
                        <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-4 py-3 font-mono text-slate-600">{student.student_id_num}</td>
                          <td className="px-4 py-3">{student.surname}</td>
                          <td className="px-4 py-3">{student.name}</td>
                          <td className="px-4 py-3 font-medium text-slate-800">{student.full_name}</td>
                          <td className="px-4 py-3 text-right">
                            <span className={cn(
                              "px-2 py-0.5 rounded-full text-xs font-medium",
                              student.confidence > 0.8 ? "bg-green-100 text-green-700" :
                                student.confidence > 0.5 ? "bg-yellow-100 text-yellow-700" :
                                  "bg-red-100 text-red-700"
                            )}>
                              {(student.confidence * 100).toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

export default App;

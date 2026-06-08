"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FileRecord {
  _id: string;
  filename: string;
  file_type: string;
  file_category: string;
  processing_status: string;
  chunk_count: number;
  uploaded_at: string;
  metadata?: {
    thumbnails?: string[];
    slide_count?: number;
    visual_slides_analyzed?: number;
    visual_summary?: Record<string, unknown>;
  };
}

export default function FilesPage() {
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [clientId, setClientId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [fileType, setFileType] = useState("brand_spec");
  const [expandedFile, setExpandedFile] = useState<string | null>(null);

  const loadFiles = async () => {
    if (!clientId) return;
    const result = await api.listFiles(clientId);
    setFiles(result as FileRecord[]);
  };

  useEffect(() => {
    if (clientId) loadFiles();
  }, [clientId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !clientId) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("client_id", clientId);
    formData.append("file_type", fileType);

    await api.uploadFile(formData);
    setUploading(false);
    loadFiles();
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: "bg-gray-100 text-gray-700",
      processing: "bg-blue-100 text-blue-700",
      done: "bg-green-100 text-green-700",
      failed: "bg-red-100 text-red-700",
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded ${colors[status] || "bg-gray-100"}`}>
        {status}
      </span>
    );
  };

  const isVisualRef = (f: FileRecord) => f.file_type === "visual_ref";

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">File Library</h1>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="Client ID"
          className="border rounded px-3 py-2 text-sm w-48"
        />
        <select
          value={fileType}
          onChange={(e) => setFileType(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="brand_spec">Brand Spec</option>
          <option value="brand_history_proposal">Brand History (Proposal)</option>
          <option value="brand_history_copy">Brand History (Copy)</option>
          <option value="project_brief">Project Brief</option>
          <option value="competitor_copy">Competitor Copy</option>
          <option value="visual_ref">Visual Reference</option>
        </select>
        <label className="px-4 py-2 bg-blue-600 text-white rounded text-sm cursor-pointer hover:bg-blue-700">
          {uploading ? "Uploading..." : "Upload File"}
          <input
            type="file"
            accept=".pdf,.docx,.pptx"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading || !clientId}
          />
        </label>
      </div>

      {files.length === 0 ? (
        <p className="text-gray-500 text-sm">No files found. Enter a Client ID and upload files.</p>
      ) : (
        <div className="space-y-3">
          {files.map((f) => (
            <div key={f._id} className="border rounded">
              <div
                className="p-3 flex items-center gap-4 cursor-pointer hover:bg-gray-50"
                onClick={() => setExpandedFile(expandedFile === f._id ? null : f._id)}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{f.filename}</span>
                    {isVisualRef(f) && (
                      <span className="text-xs bg-violet-100 text-violet-700 px-1.5 py-0.5 rounded">visual</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {f.file_type} · {f.file_category}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {statusBadge(f.processing_status)}
                  <span className="text-xs text-gray-500">{f.chunk_count} chunks</span>
                </div>
              </div>

              {/* Expanded: show thumbnails for visual_ref files */}
              {expandedFile === f._id && isVisualRef(f) && f.metadata && (
                <div className="px-3 pb-3 border-t">
                  {f.metadata.slide_count && (
                    <p className="text-xs text-gray-500 mt-2 mb-2">
                      {f.metadata.slide_count} slides rendered · {f.metadata.visual_slides_analyzed || 0} visual slides analyzed
                    </p>
                  )}

                  {/* Thumbnail grid */}
                  {f.metadata.thumbnails && f.metadata.thumbnails.length > 0 && (
                    <div className="grid grid-cols-4 gap-2 mb-3">
                      {f.metadata.thumbnails.map((thumb, i) => (
                        <div key={i} className="aspect-[16/9] bg-gray-100 rounded overflow-hidden flex items-center justify-center">
                          <img
                            src={`${API_BASE}/thumbnails/${thumb.split("/data/thumbnails/")[1] || ""}`}
                            alt={`Slide ${i + 1}`}
                            className="w-full h-full object-cover"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                          />
                          <span className="text-xs text-gray-400 absolute">Slide {i + 1}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Visual summary */}
                  {f.metadata.visual_summary && (
                    <div className="bg-violet-50 rounded p-3 text-xs">
                      <h4 className="font-medium text-violet-800 mb-1">Visual Identity Summary</h4>
                      {!!(f.metadata.visual_summary as Record<string, unknown>).style_description && (
                        <p className="text-violet-700">{String((f.metadata.visual_summary as Record<string, unknown>).style_description)}</p>
                      )}
                      {!!(f.metadata.visual_summary as Record<string, unknown>).design_language && (
                        <p className="text-violet-600 mt-1">
                          Keywords: {((f.metadata.visual_summary as Record<string, unknown>).design_language as string[]).join(", ")}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

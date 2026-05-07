"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface FileRecord {
  _id: string;
  filename: string;
  file_type: string;
  file_category: string;
  processing_status: string;
  chunk_count: number;
  uploaded_at: string;
}

export default function FilesPage() {
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [clientId, setClientId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [fileType, setFileType] = useState("brand_spec");

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

  return (
    <div className="max-w-4xl mx-auto p-8">
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
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 font-medium">Filename</th>
              <th className="text-left py-2 font-medium">Type</th>
              <th className="text-left py-2 font-medium">Status</th>
              <th className="text-left py-2 font-medium">Chunks</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f._id} className="border-b">
                <td className="py-2">{f.filename}</td>
                <td className="py-2">{f.file_type}</td>
                <td className="py-2">{statusBadge(f.processing_status)}</td>
                <td className="py-2">{f.chunk_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

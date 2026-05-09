"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Resource {
  _id: string;
  name: string;
  type: string;
  platform?: string;
  tags?: string[];
  pricing?: string;
  followers?: string;
  outlet_type?: string;
  service_type?: string;
  placement_type?: string;
}

export default function ResourcesPage() {
  const [clientId, setClientId] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [resources, setResources] = useState<Resource[]>([]);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const loadResources = async () => {
    if (!clientId) return;
    const params = new URLSearchParams({ client_id: clientId });
    if (typeFilter) params.set("type", typeFilter);
    const res = await fetch(`${API_BASE}/api/v1/resources?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    setResources(await res.json());
  };

  useEffect(() => {
    if (clientId) loadResources();
  }, [clientId, typeFilter]);

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !clientId) return;

    setImporting(true);
    setImportResult(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("client_id", clientId);

    const res = await fetch(`${API_BASE}/api/v1/resources/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    const data = await res.json();
    setImporting(false);
    setImportResult(`Imported ${data.imported || 0} resources`);
    loadResources();
  };

  const typeLabel = (type: string) => {
    const colors: Record<string, string> = {
      kol: "bg-purple-100 text-purple-700",
      koc: "bg-pink-100 text-pink-700",
      media: "bg-blue-100 text-blue-700",
      vendor: "bg-orange-100 text-orange-700",
      placement: "bg-green-100 text-green-700",
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded ${colors[type] || "bg-gray-100 text-gray-700"}`}>
        {type}
      </span>
    );
  };

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Resource Library</h1>

      <div className="flex gap-3 mb-6 items-center">
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="Client ID"
          className="border rounded px-3 py-2 text-sm w-48"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All Types</option>
          <option value="kol">KOL</option>
          <option value="koc">KOC</option>
          <option value="media">Media</option>
          <option value="vendor">Vendor</option>
          <option value="placement">Placement</option>
        </select>
        <label className="px-4 py-2 bg-green-600 text-white rounded text-sm cursor-pointer hover:bg-green-700">
          {importing ? "Importing..." : "Import Excel"}
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={handleImport}
            className="hidden"
            disabled={importing || !clientId}
          />
        </label>
        {importResult && <span className="text-sm text-green-600">{importResult}</span>}
      </div>

      {resources.length === 0 ? (
        <p className="text-gray-500 text-sm">No resources found. Enter a Client ID or import an Excel file.</p>
      ) : (
        <div className="space-y-2">
          {resources.map((r) => (
            <div key={r._id} className="border rounded p-3 flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{r.name}</span>
                  {typeLabel(r.type)}
                </div>
                <div className="text-xs text-gray-500 flex gap-4">
                  {r.platform && <span>Platform: {r.platform}</span>}
                  {r.followers && <span>Followers: {r.followers}</span>}
                  {r.outlet_type && <span>Outlet: {r.outlet_type}</span>}
                  {r.service_type && <span>Service: {r.service_type}</span>}
                  {r.placement_type && <span>Type: {r.placement_type}</span>}
                  {r.pricing && <span>Pricing: {r.pricing}</span>}
                </div>
              </div>
              {r.tags && r.tags.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {r.tags.map((tag, i) => (
                    <span key={i} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{tag}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import Link from "next/link";
import { useTranslations } from "next-intl";

interface Client {
  _id: string;
  name: string;
  industry: string | null;
  created_at: string;
}

export default function ClientsPage() {
  const t = useTranslations("clients");
  const [clients, setClients] = useState<Client[]>([]);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [creating, setCreating] = useState(false);

  const loadClients = async () => {
    try {
      const res = await apiFetch("/api/v1/clients");
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setClients(data);
    } catch {}
  };

  useEffect(() => {
    loadClients();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const res = await apiFetch("/api/v1/clients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, industry: industry || null }),
      });
      if (!res.ok) return;
      setName("");
      setIndustry("");
      await loadClients();
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-1">{t("title")}</h1>
      <p className="text-sm text-gray-500 mb-6">
        {t("subtitle")}
      </p>

      <form onSubmit={handleCreate} className="flex gap-3 mb-8">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("namePlaceholder")}
          className="border rounded px-3 py-2 text-sm flex-1"
          required
        />
        <input
          type="text"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          placeholder={t("industryPlaceholder")}
          className="border rounded px-3 py-2 text-sm w-48"
        />
        <button
          type="submit"
          disabled={creating}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium"
        >
          {t("addClient")}
        </button>
      </form>

      {clients.length === 0 ? (
        <p className="text-gray-500 text-sm">{t("noClients")}</p>
      ) : (
        <div className="space-y-2">
          {clients.map((client) => (
            <div key={client._id} className="border rounded p-4 hover:bg-gray-50 transition-colors">
              <div className="flex items-center justify-between">
                <Link href={`/clients/${client._id}`} className="flex-1 min-w-0 group">
                  <h3 className="font-medium group-hover:text-blue-600 transition-colors">{client.name}</h3>
                  {client.industry && (
                    <p className="text-sm text-gray-500">{client.industry}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-0.5 group-hover:text-blue-400 transition-colors">
                    {t("manageHint")}
                  </p>
                </Link>
                <div className="flex items-center gap-3 ml-4 shrink-0">
                  <button
                    onClick={() => navigator.clipboard.writeText(client._id)}
                    title={t("copyId")}
                    className="flex items-center gap-1.5 font-mono text-xs text-gray-400 hover:text-gray-700 border border-dashed border-gray-300 rounded px-2 py-1 hover:border-gray-400 transition-colors"
                  >
                    <span>{client._id.slice(-8)}</span>
                    <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                      <path d="M4 2a2 2 0 00-2 2v8a2 2 0 002 2h5a2 2 0 002-2v-1h1a2 2 0 002-2V6.414a1 1 0 00-.293-.707l-3.414-3.414A1 1 0 009.586 2H4zm5 1.5V6h2.5L9 3.5zM3 4a1 1 0 011-1h4v3a1 1 0 001 1h3v4a1 1 0 01-1 1H4a1 1 0 01-1-1V4z"/>
                    </svg>
                  </button>
                  <span className="text-xs text-gray-400">
                    {new Date(client.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

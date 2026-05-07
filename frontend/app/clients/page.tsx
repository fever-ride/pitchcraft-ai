"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

interface Client {
  _id: string;
  name: string;
  industry: string | null;
  created_at: string;
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [creating, setCreating] = useState(false);

  const loadClients = async () => {
    try {
      const data = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/clients`,
        { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }
      ).then((r) => r.json());
      setClients(data);
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
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/clients`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
          body: JSON.stringify({ name, industry: industry || null }),
        }
      );
      setName("");
      setIndustry("");
      loadClients();
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Clients</h1>

      <form onSubmit={handleCreate} className="flex gap-3 mb-8">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Client name"
          className="border rounded px-3 py-2 text-sm flex-1"
          required
        />
        <input
          type="text"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          placeholder="Industry (optional)"
          className="border rounded px-3 py-2 text-sm w-48"
        />
        <button
          type="submit"
          disabled={creating}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium"
        >
          Add Client
        </button>
      </form>

      {clients.length === 0 ? (
        <p className="text-gray-500 text-sm">No clients yet.</p>
      ) : (
        <div className="space-y-2">
          {clients.map((client) => (
            <Link
              key={client._id}
              href={`/clients/${client._id}`}
              className="block border rounded p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium">{client.name}</h3>
                  {client.industry && (
                    <p className="text-sm text-gray-500">{client.industry}</p>
                  )}
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(client.created_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

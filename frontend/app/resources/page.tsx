"use client";

import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useTranslations } from "next-intl";

import type { AppDispatch, RootState } from "@/store/store";
import {
  fetchResources,
  importExcel,
  setClientId,
  setTypeFilter,
  clearImportResult,
} from "@/store/resourcesSlice";
import { addToast } from "@/store/toastSlice";

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

export default function ResourcesPage() {
  const t = useTranslations("resources");
  const dispatch = useDispatch<AppDispatch>();
  const { resources, loading, importing, importResult, clientId, typeFilter } = useSelector(
    (state: RootState) => state.resources
  );

  useEffect(() => {
    if (clientId) {
      dispatch(fetchResources({ clientId, typeFilter }));
    }
  }, [dispatch, clientId, typeFilter]);

  useEffect(() => {
    if (importResult) {
      dispatch(addToast({ message: importResult, type: "success" }));
      dispatch(clearImportResult());
      dispatch(fetchResources({ clientId, typeFilter }));
    }
  }, [importResult]);

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !clientId) return;
    dispatch(importExcel({ file, clientId }));
    e.target.value = "";
  };

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>

      <div className="flex gap-3 mb-6 items-center">
        <input
          type="text"
          value={clientId}
          onChange={(e) => dispatch(setClientId(e.target.value))}
          placeholder={t("clientIdPlaceholder")}
          className="border rounded px-3 py-2 text-sm w-48"
        />
        <select
          value={typeFilter}
          onChange={(e) => dispatch(setTypeFilter(e.target.value))}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">{t("allTypes")}</option>
          <option value="kol">KOL</option>
          <option value="koc">KOC</option>
          <option value="media">Media</option>
          <option value="vendor">Vendor</option>
          <option value="placement">Placement</option>
        </select>
        <label className="px-4 py-2 bg-green-600 text-white rounded text-sm cursor-pointer hover:bg-green-700">
          {importing ? t("importing") : t("importExcel")}
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={handleImport}
            className="hidden"
            disabled={importing || !clientId}
          />
        </label>
      </div>

      {loading && <p className="text-gray-500 text-sm">{t("loading")}</p>}

      {!loading && resources.length === 0 && (
        <p className="text-gray-500 text-sm">{t("noResources")}</p>
      )}

      {!loading && resources.length > 0 && (
        <div className="space-y-2">
          {resources.map((r) => (
            <div key={r._id} className="border rounded p-3 flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{r.name}</span>
                  {typeLabel(r.type)}
                </div>
                <div className="text-xs text-gray-500 flex gap-4">
                  {r.platforms && r.platforms.length > 0 && (
                    <span className="flex gap-1 flex-wrap">
                      {r.platforms.map((p: { name: string; followers_count?: number }) => (
                        <span key={p.name} className="text-xs text-gray-500">
                          {p.name}{p.followers_count ? ` ${(p.followers_count / 10000).toFixed(1)}万` : ""}
                        </span>
                      ))}
                    </span>
                  )}
                  {r.outlet_type && <span>{t("outlet")}{r.outlet_type}</span>}
                  {r.service_type && <span>{t("service")}{r.service_type}</span>}
                  {r.placement_type && <span>{t("type")}{r.placement_type}</span>}
                  {r.pricing && <span>{t("pricing")}{r.pricing}</span>}
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

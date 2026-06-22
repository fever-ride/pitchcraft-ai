"use client";

import { useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useTranslations } from "next-intl";

import type { AppDispatch, RootState } from "@/store/store";
import {
  fetchResources,
  importExcel,
  setScope,
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
  const { resources, loading, importing, importResult, error, scope, clientId, typeFilter } =
    useSelector((state: RootState) => state.resources);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch whenever scope / clientId / typeFilter changes
  useEffect(() => {
    if (scope === "shared" || (scope === "client" && clientId)) {
      dispatch(fetchResources({ scope, clientId, typeFilter }));
    }
  }, [dispatch, scope, clientId, typeFilter]);

  // Toast on successful import, then reload
  useEffect(() => {
    if (importResult) {
      dispatch(addToast({ message: importResult, type: "success" }));
      dispatch(clearImportResult());
      dispatch(fetchResources({ scope, clientId, typeFilter }));
    }
  }, [importResult]);

  // Toast on import/fetch errors
  useEffect(() => {
    if (error) {
      dispatch(addToast({ message: error, type: "error" }));
    }
  }, [error]);

  const handleImportClick = () => {
    // Guard: client scope requires a clientId
    if (scope === "client" && !clientId) {
      dispatch(addToast({ message: t("needClientId"), type: "error" }));
      return;
    }
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    dispatch(importExcel({ file, scope, clientId }));
    e.target.value = "";
  };

  const emptyMessage = scope === "shared" ? t("noResourcesShared") : t("noResourcesClient");

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>

      {/* Scope toggle */}
      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => dispatch(setScope("shared"))}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            scope === "shared"
              ? "bg-white shadow text-gray-900"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("agencyPool")}
        </button>
        <button
          onClick={() => dispatch(setScope("client"))}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            scope === "client"
              ? "bg-white shadow text-gray-900"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("clientResources")}
        </button>
      </div>

      {/* Filters row */}
      <div className="flex gap-3 mb-6 items-center flex-wrap">
        {scope === "client" && (
          <input
            type="text"
            value={clientId}
            onChange={(e) => dispatch(setClientId(e.target.value))}
            placeholder={t("clientIdPlaceholder")}
            className="border rounded px-3 py-2 text-sm w-48"
          />
        )}
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

        {/* Import button — always clickable, guard fires toast on bad state */}
        <button
          onClick={handleImportClick}
          disabled={importing}
          className="px-4 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {importing ? t("importing") : t("importExcel")}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>

      {loading && <p className="text-gray-500 text-sm">{t("loading")}</p>}

      {!loading && scope === "client" && !clientId && (
        <p className="text-gray-400 text-sm italic">{t("needClientId")}</p>
      )}

      {!loading && (scope === "shared" || clientId) && resources.length === 0 && (
        <p className="text-gray-500 text-sm">{emptyMessage}</p>
      )}

      {!loading && resources.length > 0 && (
        <div className="space-y-2">
          {resources.map((r) => (
            <div key={r._id} className="border rounded p-3 flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{r.name}</span>
                  {typeLabel(r.type)}
                  {r.scope === "client" && (
                    <span className="text-xs bg-blue-50 text-blue-500 px-1.5 py-0.5 rounded border border-blue-200">
                      client
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-500 flex gap-4 flex-wrap">
                  {r.platforms && r.platforms.length > 0 && (
                    <span className="flex gap-2 flex-wrap">
                      {r.platforms.map((p: { name: string; followers_count?: number }) => (
                        <span key={p.name} className="text-xs text-gray-500">
                          {p.name}
                          {p.followers_count
                            ? ` ${(p.followers_count / 10000).toFixed(1)}万`
                            : ""}
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
                    <span
                      key={i}
                      className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded"
                    >
                      {tag}
                    </span>
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

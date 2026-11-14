"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  Database,
  Table as TableIcon,
  RotateCw,
  Loader2,
  Layers,
  Key,
  ExternalLink,
} from "lucide-react";
import { getDataSourceSchema, syncDataSourceSchema, DataSourceSchemaInfo } from "@/lib/api";

interface SchemaViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  datasourceId: string;
  datasourceName: string;
}

export function SchemaViewerModal({
  isOpen,
  onClose,
  datasourceId,
  datasourceName,
}: SchemaViewerModalProps) {
  const [schemaInfo, setSchemaInfo] = useState<DataSourceSchemaInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && datasourceId) {
      loadSchema();
    }
  }, [isOpen, datasourceId]);

  const loadSchema = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDataSourceSchema(datasourceId);
      setSchemaInfo(data);
    } catch (err: any) {
      setError(err.message || "Failed to load database schema.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await syncDataSourceSchema(datasourceId);
      await loadSchema();
    } catch (err: any) {
      setError(err.message || "Failed to synchronize schema.");
    } finally {
      setIsSyncing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-3xl rounded-2xl border border-slate-800 bg-[#0c1220] p-6 shadow-2xl shadow-indigo-950/40 text-slate-200 max-h-[85vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 pr-8">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">{datasourceName}</h2>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                  {schemaInfo?.dialect || "postgresql"}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {schemaInfo?.tables_indexed ?? 0} tables indexed in ChromaDB vector store
              </p>
            </div>
          </div>

          <button
            onClick={handleSync}
            disabled={isSyncing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-200 disabled:opacity-50 transition-colors"
          >
            <RotateCw className={`h-3.5 w-3.5 text-indigo-400 ${isSyncing ? "animate-spin" : ""}`} />
            <span>{isSyncing ? "Syncing..." : "Sync Schema"}</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-slate-400">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-500 mb-2" />
              <p className="text-xs">Loading schema catalog cards...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-800/40 text-xs text-rose-300">
              {error}
            </div>
          ) : schemaInfo && schemaInfo.table_cards.length > 0 ? (
            schemaInfo.table_cards.map((card, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 text-xs font-mono whitespace-pre-wrap leading-relaxed text-slate-300"
              >
                {card}
              </div>
            ))
          ) : (
            <div className="text-center py-12 text-slate-500 text-xs">
              No schema cards indexed yet. Click &quot;Sync Schema&quot; to inspect tables.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

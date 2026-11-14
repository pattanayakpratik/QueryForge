"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Database,
  ChevronDown,
  Plus,
  Check,
  Trash2,
  Layers,
  Sparkles,
} from "lucide-react";
import { DataSourceInfo } from "@/lib/api";

interface DatabaseSelectorProps {
  activeDatasource: DataSourceInfo;
  datasources: DataSourceInfo[];
  onSelectDatasource: (ds: DataSourceInfo) => void;
  onOpenConnectModal: () => void;
  onOpenSchemaModal: () => void;
  onDeleteDatasource: (dsId: string) => void;
}

export function DatabaseSelector({
  activeDatasource,
  datasources,
  onSelectDatasource,
  onOpenConnectModal,
  onOpenSchemaModal,
  onDeleteDatasource,
}: DatabaseSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (ds: DataSourceInfo) => {
    onSelectDatasource(ds);
    setIsOpen(false);
  };

  const handleDelete = (e: React.MouseEvent, dsId: string) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to remove this database from QueryForge?")) {
      onDeleteDatasource(dsId);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Current Active Database Pill / Trigger */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/80 text-slate-200 transition-all text-xs"
        title="Active Database Connection"
      >
        <Database className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
        <span className="font-semibold text-white max-w-[140px] truncate">
          {activeDatasource.name}
        </span>
        <span className="text-[10px] text-slate-400 px-1.5 py-0.2 rounded bg-black/40 border border-slate-800">
          {activeDatasource.tables_indexed} {activeDatasource.tables_indexed === 1 ? "tbl" : "tbls"}
        </span>
        <ChevronDown className={`h-3 w-3 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute left-0 sm:right-0 sm:left-auto mt-2 w-72 rounded-xl bg-[#0c1220] border border-slate-800 shadow-2xl shadow-indigo-950/40 p-2 z-50 text-xs text-slate-300 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span>Target Databases</span>
            <span className="text-slate-400 font-mono">Read-Only</span>
          </div>

          <div className="space-y-1 my-1 max-h-56 overflow-y-auto">
            {datasources.map((ds) => {
              const isActive = ds.id === activeDatasource.id;
              const isDefault = ds.id === "default-demo-db";

              return (
                <div
                  key={ds.id}
                  onClick={() => handleSelect(ds)}
                  className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${
                    isActive
                      ? "bg-indigo-600/15 border border-indigo-500/30 text-white"
                      : "hover:bg-slate-900 border border-transparent text-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Database className={`h-3.5 w-3.5 shrink-0 ${isActive ? "text-indigo-400" : "text-slate-500"}`} />
                    <div className="min-w-0">
                      <div className="font-medium truncate flex items-center gap-1.5">
                        <span>{ds.name}</span>
                        {isDefault && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                            Demo
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-2">
                        <span>{ds.dialect}</span>
                        <span>•</span>
                        <span>{ds.tables_indexed} tables</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    {isActive && <Check className="h-3.5 w-3.5 text-indigo-400" />}
                    {!isDefault && (
                      <button
                        type="button"
                        onClick={(e) => handleDelete(e, ds.id)}
                        className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                        title="Delete database connection"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pt-2 border-t border-slate-800/80 space-y-1">
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenSchemaModal();
              }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-900 transition-colors"
            >
              <Layers className="h-3.5 w-3.5 text-indigo-400" />
              <span>Inspect Schema Cards</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenConnectModal();
              }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Connect New Database...</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import React from "react";
import { ShieldCheck, ShieldAlert, Cpu, Github, Zap } from "lucide-react";
import { DatabaseSelector } from "@/components/DatabaseSelector";
import { DataSourceInfo } from "@/lib/api";

interface HeaderProps {
  activeDatasource: DataSourceInfo;
  datasources: DataSourceInfo[];
  onSelectDatasource: (ds: DataSourceInfo) => void;
  onOpenConnectModal: () => void;
  onOpenSchemaModal: () => void;
  onDeleteDatasource: (dsId: string) => void;
  studioMode: "read_only" | "read_write";
  onToggleStudioMode: (mode: "read_only" | "read_write") => void;
}

export function Header({
  activeDatasource,
  datasources,
  onSelectDatasource,
  onOpenConnectModal,
  onOpenSchemaModal,
  onDeleteDatasource,
  studioMode,
  onToggleStudioMode,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-[#0c1220]/80 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-[1.5px] shadow-lg shadow-indigo-500/20">
            <div className="h-full w-full bg-[#090d16] rounded-[7px] flex items-center justify-center">
              <Zap className="h-5 w-5 text-indigo-400 fill-indigo-400/20" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white">QueryForge</h1>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                AI Microservice
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Autonomous Text-to-SQL & Natural Language BI Engine
            </p>
          </div>
        </div>

        {/* Telemetry & Badges */}
        <div className="flex items-center gap-2.5 text-xs">
          {/* Active Target DB Selector */}
          <DatabaseSelector
            activeDatasource={activeDatasource}
            datasources={datasources}
            onSelectDatasource={onSelectDatasource}
            onOpenConnectModal={onOpenConnectModal}
            onOpenSchemaModal={onOpenSchemaModal}
            onDeleteDatasource={onDeleteDatasource}
          />

          {/* Model Router */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
            <Cpu className="h-3.5 w-3.5 text-indigo-400" />
            <span className="text-[11px] font-medium">Groq 70B <span className="text-slate-500">→</span> Gemini 1.5</span>
          </div>

          {/* Read-Only vs Read-Write Studio Mode Switcher */}
          <button
            type="button"
            onClick={() => onToggleStudioMode(studioMode === "read_only" ? "read_write" : "read_only")}
            title={
              studioMode === "read_only"
                ? "Strict Read-Only Mode (All mutations blocked by AST firewall). Click to switch to Read-Write."
                : "Read-Write Mode (Mutations permitted with Human Impact Confirmation gate). Click to switch to Read-Only."
            }
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all text-[11px] font-semibold cursor-pointer ${
              studioMode === "read_only"
                ? "bg-emerald-950/40 border-emerald-800/40 text-emerald-300 hover:bg-emerald-900/50"
                : "bg-amber-950/40 border-amber-800/50 text-amber-300 hover:bg-amber-900/50 shadow-sm shadow-amber-900/20"
            }`}
          >
            {studioMode === "read_only" ? (
              <>
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                <span>Mode: Read-Only</span>
              </>
            ) : (
              <>
                <ShieldAlert className="h-3.5 w-3.5 text-amber-400 animate-pulse" />
                <span>Mode: Read-Write (HITL)</span>
              </>
            )}
          </button>

          {/* GitHub link */}
          <a
            href="https://github.com/pattanayakpratik/QueryForge"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/70 hover:bg-slate-700/80 border border-slate-700 text-slate-200 transition-colors"
          >
            <Github className="h-3.5 w-3.5" />
            <span className="text-[11px] font-medium">Repo</span>
          </a>
        </div>
      </div>
    </header>
  );
}

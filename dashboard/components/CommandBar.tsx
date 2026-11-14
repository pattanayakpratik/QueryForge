"use client";

import React, { useState } from "react";
import { Search, Sparkles, AlertOctagon, RotateCw, ArrowRight, Loader2, ShieldAlert } from "lucide-react";
import { RECRUITER_DEMO_PROMPTS, RecruiterDemoPrompt } from "@/lib/api";

interface CommandBarProps {
  onSearch: (question: string, suggestedMode?: "read_only" | "read_write") => void;
  isLoading: boolean;
}

export function CommandBar({ onSearch, isLoading }: CommandBarProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    onSearch(query.trim());
  };

  const handleSelectDemo = (demo: RecruiterDemoPrompt) => {
    setQuery(demo.prompt);
    const suggestedMode = demo.id === "demo-write-guardrail" ? "read_write" : "read_only";
    onSearch(demo.prompt, suggestedMode);
  };

  return (
    <div className="w-full space-y-4">
      {/* Search Input Bar */}
      <form
        onSubmit={handleSubmit}
        className="relative flex items-center w-full rounded-xl bg-slate-900/90 border border-slate-800 shadow-xl shadow-indigo-950/10 focus-within:border-indigo-500/60 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all p-1.5"
      >
        <div className="pl-3 text-slate-400">
          <Search className="h-5 w-5" />
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask any natural language question (e.g. 'Show total revenue and refund rate by country for last 6 months')..."
          className="w-full bg-transparent px-3 py-2.5 text-sm sm:text-base text-white placeholder-slate-500 focus:outline-none"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 disabled:pointer-events-none text-white font-medium text-xs sm:text-sm shadow-md shadow-indigo-600/30 transition-all whitespace-nowrap"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Synthesizing...</span>
            </>
          ) : (
            <>
              <span>Run Query</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>

      {/* Recruiter 1-Click Demo Buttons */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 pt-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1">
          <Sparkles className="h-3 w-3 text-amber-400" />
          Recruiter 1-Click Demos:
        </span>
        <div className="flex flex-wrap items-center gap-2">
          {RECRUITER_DEMO_PROMPTS.map((demo) => {
            let Icon = Sparkles;
            let badgeStyle = "bg-indigo-500/10 border-indigo-500/30 hover:border-indigo-500/60 text-indigo-300";

            if (demo.id === "demo-self-healing") {
              Icon = RotateCw;
              badgeStyle = "bg-amber-500/10 border-amber-500/30 hover:border-amber-500/60 text-amber-300";
            } else if (demo.id === "demo-security-guardrail") {
              Icon = AlertOctagon;
              badgeStyle = "bg-rose-500/10 border-rose-500/30 hover:border-rose-500/60 text-rose-300";
            } else if (demo.id === "demo-write-guardrail") {
              Icon = ShieldAlert;
              badgeStyle = "bg-purple-500/10 border-purple-500/30 hover:border-purple-500/60 text-purple-300";
            }

            return (
              <button
                key={demo.id}
                type="button"
                onClick={() => handleSelectDemo(demo)}
                disabled={isLoading}
                title={demo.description}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${badgeStyle}`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{demo.label}</span>
                <span className="text-[10px] opacity-70 ml-1 px-1.5 py-0.2 rounded bg-black/30">
                  {demo.tag}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

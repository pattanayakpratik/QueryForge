"use client";

import React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  Cpu,
  Layers,
  Activity,
  RotateCw,
  Clock,
  Sparkles,
} from "lucide-react";
import { AgentStepEvent } from "@/lib/api";

interface AgentTimelineProps {
  events: AgentStepEvent[];
  isLoading: boolean;
  status?: string;
}

export function AgentTimeline({ events, isLoading, status }: AgentTimelineProps) {
  if (events.length === 0 && !isLoading) {
    return (
      <div className="h-full rounded-xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col items-center justify-center text-center">
        <div className="h-12 w-12 rounded-full bg-slate-800/80 flex items-center justify-center text-slate-500 mb-3">
          <Activity className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-300">Live Reasoning Trace</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-xs">
          Submit a natural language question above to observe Schema RAG, AST Firewall gating, and Self-Healing steps in real time.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur p-5 shadow-lg flex flex-col h-full">
      {/* Timeline Header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-white">Agent Execution Trace</h3>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[10px] animate-pulse">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400"></span>
              Streaming SSE
            </span>
          )}
          {status === "BLOCKED_AST" && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[10px] font-semibold">
              <ShieldAlert className="h-3 w-3" />
              AST BLOCKED
            </span>
          )}
          {status === "SUCCESS" && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
              <CheckCircle2 className="h-3 w-3" />
              COMPLETED
            </span>
          )}
        </div>
      </div>

      {/* Step by Step Timeline Events */}
      <div className="space-y-4 overflow-y-auto pr-1 max-h-[500px]">
        {events.map((evt, idx) => {
          const isError = evt.event_type.startsWith("error_");
          const isHeal = evt.event_type.includes("heal");
          const isAst = evt.event_type.includes("ast");
          const isCost = evt.event_type.includes("cost");
          const isCompleted = evt.event_type === "step_completed";

          let Icon = Activity;
          let iconColor = "text-indigo-400 bg-indigo-500/10 border-indigo-500/30";

          if (isError || evt.event_type === "error_ast") {
            Icon = ShieldAlert;
            iconColor = "text-rose-400 bg-rose-500/10 border-rose-500/30";
          } else if (isHeal) {
            Icon = RotateCw;
            iconColor = "text-amber-400 bg-amber-500/10 border-amber-500/30";
          } else if (isAst && !isError) {
            Icon = ShieldCheck;
            iconColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
          } else if (isCompleted) {
            Icon = CheckCircle2;
            iconColor = "text-cyan-400 bg-cyan-500/10 border-cyan-500/30";
          } else if (evt.event_type.includes("schema")) {
            Icon = Layers;
            iconColor = "text-blue-400 bg-blue-500/10 border-blue-500/30";
          } else if (evt.event_type.includes("sql")) {
            Icon = Cpu;
            iconColor = "text-purple-400 bg-purple-500/10 border-purple-500/30";
          }

          return (
            <div key={idx} className="relative flex items-start gap-3 text-xs group">
              {/* Vertical connector line */}
              {idx < events.length - 1 && (
                <div className="absolute left-3.5 top-7 bottom-0 w-px bg-slate-800" />
              )}

              {/* Step Icon */}
              <div
                className={`relative z-10 h-7 w-7 rounded-lg border flex items-center justify-center shrink-0 ${iconColor}`}
              >
                <Icon className="h-3.5 w-3.5" />
              </div>

              {/* Event Content */}
              <div className="flex-1 min-w-0 pt-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-200 truncate">
                    {evt.event_type.replace(/_/g, " ").toUpperCase()}
                  </span>
                  <span className="text-[10px] text-slate-500 flex items-center gap-1 shrink-0 font-mono">
                    <Clock className="h-2.5 w-2.5" />
                    +{evt.timestamp}s
                  </span>
                </div>
                <p className="text-slate-400 mt-0.5 break-words leading-relaxed">{evt.message}</p>

                {/* Badges and Payload Callouts */}
                {evt.data?.provider && (
                  <div className="flex items-center gap-1.5 mt-2">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-indigo-300 border border-slate-700">
                      Model: {evt.data.provider} ({evt.data.model || "LLaMA-3.3-70B"})
                    </span>
                  </div>
                )}

                {evt.data?.cost !== undefined && (
                  <div className="flex items-center gap-1.5 mt-1.5">
                    <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-[10px] font-mono text-emerald-400 border border-emerald-800/40">
                      EXPLAIN Cost: {evt.data.cost} (Limit: 50,000)
                    </span>
                  </div>
                )}

                {evt.data?.error && (
                  <div className="mt-2 p-2 rounded-md bg-rose-950/30 border border-rose-900/50 text-[11px] text-rose-300 font-mono break-all">
                    {evt.data.error}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

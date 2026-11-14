"use client";

import React, { useState } from "react";
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  BarChart3,
  Table as TableIcon,
  Code2,
  Download,
  Copy,
  Check,
  Sparkles,
  ShieldAlert,
  Clock,
  Layers,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  Database,
  AlertOctagon,
} from "lucide-react";
import { QueryResult } from "@/lib/api";

const PIE_COLORS = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6"];

interface DataVisualizationProps {
  result: QueryResult | null;
  isLoading: boolean;
  onConfirmMutation?: (sql: string) => Promise<void>;
  onCancelMutation?: () => void;
  isConfirmingMutation?: boolean;
}

export function DataVisualization({
  result,
  isLoading,
  onConfirmMutation,
  onCancelMutation,
  isConfirmingMutation = false,
}: DataVisualizationProps) {
  const [activeTab, setActiveTab] = useState<"chart" | "table" | "sql">("chart");
  const [copied, setCopied] = useState(false);

  const handleCopySQL = () => {
    if (result?.sql) {
      navigator.clipboard.writeText(result.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 flex flex-col items-center justify-center text-center h-full min-h-[420px]">
        <div className="relative mb-4">
          <div className="h-12 w-12 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin" />
          <Sparkles className="h-5 w-5 text-indigo-400 absolute inset-0 m-auto" />
        </div>
        <h3 className="text-sm font-semibold text-slate-200">Executing Guardrailed Synthesis</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-sm">
          Traversing AST firewall, validating schema keys, and shaping Recharts visualization...
        </p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 flex flex-col items-center justify-center text-center h-full min-h-[420px]">
        <div className="h-12 w-12 rounded-xl bg-slate-800/80 flex items-center justify-center text-slate-500 mb-3">
          <BarChart3 className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-300">Analytical Studio Workspace</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-sm">
          Run any natural language query or test a recruiter demo to render real-time interactive charts, data grids, and SQL syntax.
        </p>
      </div>
    );
  }

  // Handle AST Firewall Blocked State
  if (result.status === "BLOCKED_AST") {
    return (
      <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-8 flex flex-col items-center justify-center text-center min-h-[420px]">
        <div className="h-16 w-16 rounded-full bg-rose-900/40 border border-rose-600/40 flex items-center justify-center text-rose-400 mb-4 animate-bounce">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h3 className="text-lg font-bold text-rose-300">Security Guardrail Triggered</h3>
        <p className="text-xs font-mono uppercase tracking-wider text-rose-400 mt-1 px-2.5 py-0.5 rounded-full bg-rose-950/60 border border-rose-800/50">
          SQLGlot AST Firewall Alert (&lt;2ms)
        </p>
        <p className="text-sm text-slate-300 mt-4 max-w-md leading-relaxed">
          {result.summary || "Destructive DDL/DML statement intercepted and rejected prior to database driver dispatch."}
        </p>
        {result.sql && (
          <div className="mt-6 w-full max-w-lg p-3 rounded-lg bg-black/60 border border-rose-900/50 text-left font-mono text-xs text-rose-200 overflow-x-auto">
            {result.sql}
          </div>
        )}
      </div>
    );
  }

  // Handle Awaiting Human Confirmation State for Write/Mutation
  if (result.status === "AWAITING_CONFIRMATION") {
    const impact = result.mutation_impact;
    const isCritical = impact?.risk_level === "CRITICAL";
    const isHigh = impact?.risk_level === "HIGH";
    const isMedium = impact?.risk_level === "MEDIUM";

    let riskBadgeColor = "bg-emerald-500/10 border-emerald-500/30 text-emerald-400";
    if (isCritical) {
      riskBadgeColor = "bg-rose-500/20 border-rose-500/40 text-rose-300 animate-pulse";
    } else if (isHigh) {
      riskBadgeColor = "bg-orange-500/20 border-orange-500/40 text-orange-300";
    } else if (isMedium) {
      riskBadgeColor = "bg-amber-500/20 border-amber-500/40 text-amber-300";
    }

    return (
      <div className="rounded-xl border border-amber-800/60 bg-gradient-to-b from-amber-950/20 to-slate-900/80 p-6 flex flex-col justify-between h-full min-h-[460px] shadow-2xl">
        <div className="space-y-4">
          {/* Header Alert */}
          <div className="flex items-start justify-between gap-4 border-b border-amber-900/40 pb-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-amber-200">
                  Write Action Detected: Confirmation Required
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  QueryForge is in Read-Write mode. Review the assessed impact below before authorizing execution.
                </p>
              </div>
            </div>
            <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold border uppercase tracking-wider shrink-0 ${riskBadgeColor}`}>
              {impact?.risk_level || "MEDIUM"} Risk
            </span>
          </div>

          {/* Impact Assessment Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* What Will Be Done */}
            <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-indigo-400" />
                <span>What Will Be Done</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono text-xs font-bold">
                  {impact?.action_type || "MUTATION"}
                </span>
                <span className="text-xs text-slate-300">
                  {impact?.description || "Executes database write modification."}
                </span>
              </div>
            </div>

            {/* Target Tables & Affected Columns */}
            <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-indigo-400" />
                <span>Targeted Resources</span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="text-slate-400">Tables:</span>
                {impact?.target_tables.map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded bg-slate-800 text-slate-200 font-mono text-[11px] border border-slate-700">
                    {t}
                  </span>
                ))}
                {impact?.affected_columns && impact.affected_columns.length > 0 && (
                  <>
                    <span className="text-slate-400 ml-2">Cols:</span>
                    {impact.affected_columns.map((c) => (
                      <span key={c} className="px-2 py-0.5 rounded bg-slate-800 text-cyan-300 font-mono text-[11px] border border-slate-700">
                        {c}
                      </span>
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* Scope / WHERE Filter */}
            <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Filter Scope
              </div>
              {impact?.has_where_clause ? (
                <div className="p-2 rounded bg-slate-900 border border-slate-800 font-mono text-xs text-emerald-300 truncate">
                  WHERE {impact.where_clause_preview}
                </div>
              ) : (
                <div className="p-2 rounded bg-rose-950/40 border border-rose-800/40 font-mono text-xs text-rose-300 flex items-center gap-1.5 font-bold">
                  <AlertOctagon className="h-3.5 w-3.5 shrink-0" />
                  <span>UNFILTERED: Applies to ALL rows in table!</span>
                </div>
              )}
            </div>

            {/* Dry-Run Blast Radius */}
            <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Estimated Blast Radius</span>
                <span className="text-[10px] text-slate-500 font-normal">Dry-Run Rollback</span>
              </div>
              <div className="flex items-center gap-2">
                {impact?.estimated_affected_rows !== undefined && impact?.estimated_affected_rows !== null ? (
                  <span className="text-sm font-bold text-amber-300 font-mono">
                    ~{impact.estimated_affected_rows} row(s) affected
                  </span>
                ) : (
                  <span className="text-xs text-slate-300 font-mono">
                    Schema structure modification (DDL)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* SQL Preview Box */}
          <div className="relative rounded-lg bg-black/70 border border-slate-800 p-3.5 font-mono text-xs text-indigo-200 overflow-x-auto">
            <button
              onClick={handleCopySQL}
              className="absolute top-2.5 right-2.5 flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-sans border border-slate-700 transition-colors"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? "Copied" : "Copy SQL"}</span>
            </button>
            <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1 font-sans">
              Proposed Mutation SQL
            </span>
            <pre className="whitespace-pre-wrap">{result.sql}</pre>
          </div>
        </div>

        {/* Human Confirmation Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800/80 mt-4">
          <button
            type="button"
            onClick={onCancelMutation}
            disabled={isConfirmingMutation}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
          >
            <XCircle className="h-4 w-4" />
            <span>Cancel / Reject</span>
          </button>

          <button
            type="button"
            onClick={() => onConfirmMutation && onConfirmMutation(result.sql)}
            disabled={isConfirmingMutation}
            className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-xs font-bold shadow-lg shadow-orange-950/40 transition-all disabled:opacity-50 cursor-pointer"
          >
            {isConfirmingMutation ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Committing Changes...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                <span>Proceed & Execute Mutation</span>
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  // Handle Mutation Committed State
  if (result.status === "MUTATION_COMMITTED") {
    return (
      <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 p-8 flex flex-col items-center justify-center text-center min-h-[420px]">
        <div className="h-16 w-16 rounded-full bg-emerald-900/40 border border-emerald-600/40 flex items-center justify-center text-emerald-400 mb-4">
          <CheckCircle2 className="h-8 w-8" />
        </div>
        <h3 className="text-lg font-bold text-emerald-300">Mutation Executed & Committed</h3>
        <p className="text-xs font-mono uppercase tracking-wider text-emerald-400 mt-1 px-2.5 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-800/50">
          Transaction Committed • {result.rows_affected ?? 0} Rows Affected • {result.execution_time_ms}ms
        </p>
        <p className="text-sm text-slate-300 mt-4 max-w-md leading-relaxed">
          {result.summary || "The confirmed mutation has been successfully applied to the database and logged in the audit registry."}
        </p>
        {result.sql && (
          <div className="mt-6 w-full max-w-lg p-3 rounded-lg bg-black/60 border border-emerald-900/50 text-left font-mono text-xs text-emerald-200 overflow-x-auto">
            {result.sql}
          </div>
        )}
      </div>
    );
  }

  // Handle CSV Export with formula injection mitigation (CWE-1236)
  const handleExportCSV = () => {
    if (!result.rows || result.rows.length === 0) return;
    const headers = result.columns
      .map((col) => `"${String(col).replace(/"/g, '""')}"`)
      .join(",");

    const rows = result.rows
      .map((row) =>
        result.columns
          .map((col) => {
            const rawVal = row[col];
            if (rawVal === null || rawVal === undefined) return '""';
            let strVal = String(rawVal);
            // Neutralize spreadsheet formula injection (=, +, -, @, \t, \r)
            if (/^[=+\-@\t\r]/.test(strVal)) {
              strVal = `'${strVal}`;
            }
            return `"${strVal.replace(/"/g, '""')}"`;
          })
          .join(",")
      )
      .join("\n");

    const blob = new Blob([`${headers}\n${rows}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `queryforge_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const chart = result.chart_config;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur p-5 shadow-lg flex flex-col h-full space-y-4">
      {/* Executive Summary Card */}
      {result.summary && (
        <div className="flex items-start gap-3 p-3.5 rounded-lg bg-indigo-950/30 border border-indigo-900/40 text-xs">
          <div className="p-1 rounded bg-indigo-600/20 text-indigo-400 mt-0.5">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="flex-1">
            <span className="font-semibold text-indigo-300 uppercase tracking-wider text-[10px] block mb-0.5">
              Executive Analytical Summary
            </span>
            <p className="text-slate-300 leading-relaxed">{result.summary}</p>
          </div>
        </div>
      )}

      {/* Tabs & Controls Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-950 border border-slate-800 text-xs font-medium">
          <button
            onClick={() => setActiveTab("chart")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === "chart"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span>Visualization</span>
          </button>
          <button
            onClick={() => setActiveTab("table")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === "table"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <TableIcon className="h-3.5 w-3.5" />
            <span>Data Grid ({result.row_count})</span>
          </button>
          <button
            onClick={() => setActiveTab("sql")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
              activeTab === "sql"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Code2 className="h-3.5 w-3.5" />
            <span>Verified SQL</span>
          </button>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-2 text-[11px] text-slate-400 font-mono">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3 text-slate-500" />
              {result.execution_time_ms}ms
            </span>
            {result.explain_cost !== undefined && (
              <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                Cost: {result.explain_cost}
              </span>
            )}
          </div>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Main Tab Content Display */}
      <div className="flex-1 min-h-[340px]">
        {/* 1. Chart View */}
        {activeTab === "chart" && (
          <div className="h-full w-full flex flex-col justify-center">
            {chart?.chart_type === "kpi_card" ? (
              <div className="flex flex-col items-center justify-center p-8 text-center bg-slate-950/40 rounded-xl border border-slate-800">
                <span className="text-xs uppercase tracking-wider text-slate-400 font-medium">
                  {chart.title}
                </span>
                <span className="text-4xl sm:text-5xl font-black text-indigo-400 mt-2 font-mono">
                  {chart.data[0]?.[chart.y_axis || ""] ?? "0"}
                </span>
                <p className="text-xs text-slate-400 mt-3 max-w-sm">{chart.summary}</p>
              </div>
            ) : chart?.chart_type === "area_chart" && chart.x_axis ? (
              <div className="h-[340px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chart.data} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <defs>
                      <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey={chart.x_axis} stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0b0f19",
                        borderColor: "#1e293b",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey={chart.series[0] || chart.y_axis || "value"}
                      stroke="#6366f1"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#areaGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : chart?.chart_type === "pie_chart" && chart.x_axis ? (
              <div className="h-[340px] w-full flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0b0f19",
                        borderColor: "#1e293b",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Pie
                      data={chart.data}
                      dataKey={chart.y_axis || "value"}
                      nameKey={chart.x_axis}
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label
                    >
                      {chart.data.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : chart?.x_axis && chart?.y_axis ? (
              <div className="h-[340px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart.data} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey={chart.x_axis} stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0b0f19",
                        borderColor: "#1e293b",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey={chart.y_axis} fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[340px] flex items-center justify-center text-slate-500 text-xs">
                Tabular format recommended for multidimensional results. Switch to Data Grid tab.
              </div>
            )}
          </div>
        )}

        {/* 2. Table Data Grid View */}
        {activeTab === "table" && (
          <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/60 max-h-[380px]">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-900/90 text-slate-300 font-semibold sticky top-0 border-b border-slate-800">
                <tr>
                  {result.columns.map((col) => (
                    <th key={col} className="px-4 py-2.5 whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {result.rows.slice(0, 50).map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30 transition-colors font-mono">
                    {result.columns.map((col) => (
                      <td key={col} className="px-4 py-2 whitespace-nowrap">
                        {String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 3. Formatted SQL Syntax View */}
        {activeTab === "sql" && (
          <div className="relative rounded-lg bg-slate-950 border border-slate-800 p-4 font-mono text-xs text-indigo-200 overflow-x-auto h-[340px]">
            <button
              onClick={handleCopySQL}
              className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-sans border border-slate-700 transition-colors"
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 text-emerald-400" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  <span>Copy SQL</span>
                </>
              )}
            </button>
            <pre className="whitespace-pre-wrap leading-relaxed pt-2">{result.sql}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

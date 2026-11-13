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
} from "lucide-react";
import { QueryResult } from "@/lib/api";

const PIE_COLORS = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6"];

interface DataVisualizationProps {
  result: QueryResult | null;
  isLoading: boolean;
}

export function DataVisualization({ result, isLoading }: DataVisualizationProps) {
  const [activeTab, setActiveTab] = useState<"chart" | "table" | "sql">("chart");
  const [copied, setCopied] = useState(false);

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

  // Handle CSV Export
  const handleExportCSV = () => {
    if (!result.rows || result.rows.length === 0) return;
    const headers = result.columns.join(",");
    const rows = result.rows
      .map((row) =>
        result.columns
          .map((col) => {
            const val = row[col];
            if (val === null || val === undefined) return "";
            if (typeof val === "string" && val.includes(",")) return `"${val}"`;
            return String(val);
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

  const handleCopySQL = () => {
    navigator.clipboard.writeText(result.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

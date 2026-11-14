"use client";

import React, { useState } from "react";
import {
  X,
  Database,
  ShieldCheck,
  Zap,
  Check,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Server,
  Cloud,
  FileCode2,
} from "lucide-react";
import {
  testDatabaseConnection,
  createDataSource,
  DataSourceInfo,
  DataSourceTestResult,
} from "@/lib/api";

interface ConnectDatabaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnected: (newDs: DataSourceInfo) => void;
}

interface ProviderPreset {
  id: string;
  name: string;
  dialect: string;
  icon: any;
  badge: string;
  templateUri: string;
  hint: string;
}

const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: "supabase",
    name: "Supabase",
    dialect: "postgresql",
    icon: Zap,
    badge: "Cloud Postgres",
    templateUri: "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require",
    hint: "Found under Project Settings → Database → Connection string (URI). Ensure port 5432 or 6543 (pooler) is used.",
  },
  {
    id: "neon",
    name: "Neon Serverless",
    dialect: "postgresql",
    icon: Cloud,
    badge: "Serverless Postgres",
    templateUri: "postgresql://[USER]:[PASSWORD]@[ENDPOINT-ID].neon.tech/[DBNAME]?sslmode=require",
    hint: "Copy connection string from your Neon Dashboard. 'sslmode=require' is automatically mapped.",
  },
  {
    id: "aws-rds",
    name: "AWS RDS / Generic Postgres",
    dialect: "postgresql",
    icon: Server,
    badge: "PostgreSQL 14-17",
    templateUri: "postgresql://postgres:[PASSWORD]@[RDS-ENDPOINT].rds.amazonaws.com:5432/[DBNAME]",
    hint: "Verify your RDS Security Group allows inbound connections from your network/host.",
  },
  {
    id: "sqlite",
    name: "SQLite Local / Embedded",
    dialect: "sqlite",
    icon: FileCode2,
    badge: "File / Embedded",
    templateUri: "sqlite:///./analytics.db",
    hint: "Path to an existing SQLite database file (.db, .sqlite, .sqlite3).",
  },
];

export function ConnectDatabaseModal({
  isOpen,
  onClose,
  onConnected,
}: ConnectDatabaseModalProps) {
  const [name, setName] = useState("");
  const [dialect, setDialect] = useState("postgresql");
  const [connectionUri, setConnectionUri] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<DataSourceTestResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSelectPreset = (preset: ProviderPreset) => {
    setDialect(preset.dialect);
    setConnectionUri(preset.templateUri);
    if (!name) {
      setName(`My ${preset.name} DB`);
    }
    setTestResult(null);
    setTestError(null);
  };

  const handleTestConnection = async () => {
    if (!connectionUri.trim()) return;
    setIsTesting(true);
    setTestResult(null);
    setTestError(null);

    try {
      const res = await testDatabaseConnection({
        name: name || "Test DB",
        connection_uri: connectionUri.trim(),
        dialect,
      });

      if (res.success) {
        setTestResult(res);
        setDialect(res.dialect);
      } else {
        setTestError(res.message);
      }
    } catch (err: any) {
      setTestError(err.message || "Failed to establish read-only test connection.");
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveAndConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !connectionUri.trim()) return;

    setIsSaving(true);
    setSaveError(null);

    try {
      const created = await createDataSource({
        name: name.trim(),
        connection_uri: connectionUri.trim(),
        dialect,
      });

      onConnected(created);
      onClose();
    } catch (err: any) {
      setSaveError(err.message || "Failed to register database.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl rounded-2xl border border-slate-800 bg-[#0c1220] p-6 shadow-2xl shadow-indigo-950/40 text-slate-200 max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight">Connect Your Database</h2>
            <p className="text-xs text-slate-400">
              Provide any PostgreSQL or SQLite connection URL for autonomous Schema RAG and natural language queries.
            </p>
          </div>
        </div>

        {/* Read-Only Safety Guarantee Banner */}
        <div className="mb-5 p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/40 flex items-start gap-2.5">
          <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-semibold text-emerald-300">Strict Read-Only Guarantee: </span>
            <span className="text-emerald-400/90">
              QueryForge will <strong className="text-white">NEVER write, modify, or alter</strong> your database.
              Every connection is sandboxed with <code className="px-1 py-0.5 rounded bg-emerald-900/40 text-emerald-300">SET LOCAL TRANSACTION READ ONLY</code> and compile-time AST firewall protection.
            </span>
          </div>
        </div>

        {/* 1-Click Provider Presets */}
        <div className="mb-5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            1-Click Provider Templates
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {PROVIDER_PRESETS.map((preset) => {
              const Icon = preset.icon;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handleSelectPreset(preset)}
                  className="flex flex-col items-start p-2.5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/70 hover:border-indigo-500/40 transition-all text-left group"
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <Icon className="h-3.5 w-3.5 text-indigo-400 group-hover:text-indigo-300" />
                    <span className="text-xs font-semibold text-slate-200 group-hover:text-white">
                      {preset.name}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 group-hover:text-slate-400">
                    {preset.badge}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Connection Form */}
        <form onSubmit={handleSaveAndConnect} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Database Name */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Database Display Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Supabase Production, Analytics DB"
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                required
              />
            </div>

            {/* Dialect */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Dialect
              </label>
              <select
                value={dialect}
                onChange={(e) => setDialect(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
              >
                <option value="postgresql">PostgreSQL</option>
                <option value="sqlite">SQLite</option>
              </select>
            </div>
          </div>

          {/* Connection URL Input */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-medium text-slate-300">
                Database Connection URL
              </label>
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
              >
                {showPassword ? (
                  <>
                    <EyeOff className="h-3 w-3" />
                    <span>Hide Credentials</span>
                  </>
                ) : (
                  <>
                    <Eye className="h-3 w-3" />
                    <span>Show Credentials</span>
                  </>
                )}
              </button>
            </div>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={connectionUri}
                onChange={(e) => {
                  setConnectionUri(e.target.value);
                  setTestResult(null);
                  setTestError(null);
                }}
                placeholder="postgresql://user:password@host:5432/dbname"
                className="w-full font-mono text-xs px-3 py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                required
              />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Supports <code className="text-slate-400">postgres://</code>, <code className="text-slate-400">postgresql://</code>, and <code className="text-slate-400">sqlite:///</code>. Credentials are encrypted via Fernet AES-128.
            </p>
          </div>

          {/* Test Connection Probe Outcome */}
          {testResult && (
            <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-800/40 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 font-semibold text-emerald-400">
                  <Check className="h-4 w-4" />
                  Connection Verified Read-Only!
                </span>
                <span className="font-mono text-[11px] text-emerald-400 px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/50">
                  ⚡ {testResult.latency_ms}ms
                </span>
              </div>
              <p className="text-xs text-slate-300">{testResult.message}</p>
              {testResult.tables_found.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {testResult.tables_found.slice(0, 10).map((tbl) => (
                    <span
                      key={tbl}
                      className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300"
                    >
                      {tbl}
                    </span>
                  ))}
                  {testResult.tables_found.length > 10 && (
                    <span className="text-[11px] text-slate-400 px-1 py-0.5">
                      +{testResult.tables_found.length - 10} more
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {testError && (
            <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-800/40 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-rose-200">Connection Failed: </span>
                <span>{testError}</span>
              </div>
            </div>
          )}

          {saveError && (
            <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-800/40 text-xs text-rose-300">
              {saveError}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800/80">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={isTesting || !connectionUri.trim()}
              className="px-4 py-2 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-semibold text-slate-200 disabled:opacity-50 transition-colors flex items-center gap-1.5"
            >
              {isTesting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Probing DB...</span>
                </>
              ) : (
                <>
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  <span>Test Connection</span>
                </>
              )}
            </button>

            <button
              type="submit"
              disabled={isSaving || !name.trim() || !connectionUri.trim()}
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-xs font-semibold text-white shadow-md shadow-indigo-600/30 disabled:opacity-50 transition-all flex items-center gap-1.5"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Indexing Schema...</span>
                </>
              ) : (
                <>
                  <Check className="h-3.5 w-3.5" />
                  <span>Connect & Activate</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

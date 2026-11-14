"use client";

import React, { useState, useEffect } from "react";
import { Header } from "@/components/Header";
import { CommandBar } from "@/components/CommandBar";
import { AgentTimeline } from "@/components/AgentTimeline";
import { DataVisualization } from "@/components/DataVisualization";
import { ConnectDatabaseModal } from "@/components/ConnectDatabaseModal";
import { SchemaViewerModal } from "@/components/SchemaViewerModal";
import {
  streamQueryExecution,
  confirmMutationExecution,
  fetchDataSources,
  deleteDataSource,
  AgentStepEvent,
  QueryResult,
  DataSourceInfo,
} from "@/lib/api";

const DEFAULT_DATASOURCE: DataSourceInfo = {
  id: "default-demo-db",
  name: "Demo SaaS & E-Commerce DB",
  dialect: "postgresql",
  tables_indexed: 5,
  created_at: new Date().toISOString(),
};

export default function Home() {
  const [datasources, setDatasources] = useState<DataSourceInfo[]>([DEFAULT_DATASOURCE]);
  const [activeDatasource, setActiveDatasource] = useState<DataSourceInfo>(DEFAULT_DATASOURCE);
  const [studioMode, setStudioMode] = useState<"read_only" | "read_write">("read_only");

  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isSchemaModalOpen, setIsSchemaModalOpen] = useState(false);

  const [events, setEvents] = useState<AgentStepEvent[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConfirmingMutation, setIsConfirmingMutation] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState("");

  useEffect(() => {
    loadDataSources();
  }, []);

  const loadDataSources = async () => {
    try {
      const list = await fetchDataSources();
      if (list && list.length > 0) {
        setDatasources(list);
        const match = list.find((ds) => ds.id === activeDatasource.id) || list[0];
        setActiveDatasource(match);
      }
    } catch (err) {
      console.warn("Failed to load datasources", err);
    }
  };

  const handleConnectedNewDataSource = (newDs: DataSourceInfo) => {
    setDatasources((prev) => [newDs, ...prev.filter((d) => d.id !== newDs.id)]);
    setActiveDatasource(newDs);
    setResult(null);
    setEvents([]);
  };

  const handleDeleteDataSource = async (dsId: string) => {
    try {
      await deleteDataSource(dsId);
      setDatasources((prev) => prev.filter((d) => d.id !== dsId));
      if (activeDatasource.id === dsId) {
        const fallback = datasources.find((d) => d.id !== dsId) || DEFAULT_DATASOURCE;
        setActiveDatasource(fallback);
      }
    } catch (err: any) {
      alert(err.message || "Failed to delete data source.");
    }
  };

  const handleRunQuery = async (
    question: string,
    suggestedMode?: "read_only" | "read_write"
  ) => {
    const modeToUse = suggestedMode || studioMode;
    if (suggestedMode && suggestedMode !== studioMode) {
      setStudioMode(suggestedMode);
    }
    setActiveQuestion(question);
    setIsLoading(true);
    setEvents([]);
    setResult(null);

    await streamQueryExecution(
      activeDatasource.id,
      question,
      (newEvent) => {
        setEvents((prev) => [...prev, newEvent]);
      },
      (completedResult) => {
        setResult(completedResult);
        setIsLoading(false);
      },
      (errorMsg) => {
        setIsLoading(false);
      },
      modeToUse
    );
  };

  const handleConfirmMutation = async (sql: string) => {
    setIsConfirmingMutation(true);
    try {
      const confirmRes = await confirmMutationExecution({
        datasourceId: activeDatasource.id,
        sql,
      });

      const committedResult: QueryResult = {
        sql: confirmRes.sql,
        columns: [],
        rows: [],
        row_count: confirmRes.rows_affected,
        rows_affected: confirmRes.rows_affected,
        execution_time_ms: confirmRes.execution_time_ms,
        provider_used: "USER_CONFIRMED",
        self_heal_attempts: 0,
        status: "MUTATION_COMMITTED",
        summary: confirmRes.message,
      };

      setResult(committedResult);

      setEvents((prev) => [
        ...prev,
        {
          event_type: "step_mutation_committed",
          step_number: prev.length + 1,
          message: `Mutation Committed: ${confirmRes.rows_affected} row(s) affected (${confirmRes.execution_time_ms}ms).`,
          data: {
            status: "MUTATION_COMMITTED",
            rows_affected: confirmRes.rows_affected,
            execution_time_ms: confirmRes.execution_time_ms,
          },
          timestamp: Number((performance.now() / 1000).toFixed(2)),
        },
      ]);
    } catch (err: any) {
      alert(err.message || "Failed to commit mutation.");
    } finally {
      setIsConfirmingMutation(false);
    }
  };

  const handleCancelMutation = () => {
    setResult(null);
    setEvents((prev) => [
      ...prev,
      {
        event_type: "step_mutation_cancelled",
        step_number: prev.length + 1,
        message: "Write mutation discarded by user. No database changes were applied.",
        data: { status: "CANCELLED" },
        timestamp: Number((performance.now() / 1000).toFixed(2)),
      },
    ]);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100">
      {/* Navigation Header with Active Database Switcher & Mode Toggle */}
      <Header
        activeDatasource={activeDatasource}
        datasources={datasources}
        onSelectDatasource={setActiveDatasource}
        onOpenConnectModal={() => setIsConnectModalOpen(true)}
        onOpenSchemaModal={() => setIsSchemaModalOpen(true)}
        onDeleteDatasource={handleDeleteDataSource}
        studioMode={studioMode}
        onToggleStudioMode={setStudioMode}
      />

      {/* Main Studio Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        {/* Panel 1: Natural Language Command Bar & 1-Click Recruiter Demos */}
        <section>
          <CommandBar onSearch={handleRunQuery} isLoading={isLoading} />
        </section>

        {/* Studio Workspace Grid: Panel 2 (Timeline) & Panel 3 (Visualizations) */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 items-start">
          {/* Panel 2: Live Agent Reasoning Trace */}
          <div className="lg:col-span-5 h-full">
            <AgentTimeline
              events={events}
              isLoading={isLoading}
              status={result?.status}
            />
          </div>

          {/* Panel 3: Dynamic Chart, Data Grid, and SQL Syntax */}
          <div className="lg:col-span-7 h-full">
            <DataVisualization
              result={result}
              isLoading={isLoading}
              onConfirmMutation={handleConfirmMutation}
              onCancelMutation={handleCancelMutation}
              isConfirmingMutation={isConfirmingMutation}
            />
          </div>
        </section>
      </main>

      {/* Connect Database Modal */}
      <ConnectDatabaseModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        onConnected={handleConnectedNewDataSource}
      />

      {/* Inspect Schema Modal */}
      <SchemaViewerModal
        isOpen={isSchemaModalOpen}
        onClose={() => setIsSchemaModalOpen(false)}
        datasourceId={activeDatasource.id}
        datasourceName={activeDatasource.name}
      />

      {/* Footer */}
      <footer className="border-t border-slate-900/80 py-4 text-center text-xs text-slate-600">
        <p>
          QueryForge Standalone AI Microservice · Built with Next.js 16, SQLGlot, ChromaDB & Groq LLaMA-3.3-70B
        </p>
      </footer>
    </div>
  );
}

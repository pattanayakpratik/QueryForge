"use client";

import React, { useState } from "react";
import { Header } from "@/components/Header";
import { CommandBar } from "@/components/CommandBar";
import { AgentTimeline } from "@/components/AgentTimeline";
import { DataVisualization } from "@/components/DataVisualization";
import { streamQueryExecution, AgentStepEvent, QueryResult } from "@/lib/api";

export default function Home() {
  const [events, setEvents] = useState<AgentStepEvent[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState("");

  const handleRunQuery = async (question: string) => {
    setActiveQuestion(question);
    setIsLoading(true);
    setEvents([]);
    setResult(null);

    const datasourceId = "default-demo-db";

    await streamQueryExecution(
      datasourceId,
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
      }
    );
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100">
      {/* Navigation Header */}
      <Header />

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
            <DataVisualization result={result} isLoading={isLoading} />
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900/80 py-4 text-center text-xs text-slate-600">
        <p>
          QueryForge Standalone AI Microservice · Built with Next.js 16, SQLGlot, ChromaDB & Groq LLaMA-3.3-70B
        </p>
      </footer>
    </div>
  );
}

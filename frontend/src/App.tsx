import { useState, useCallback } from "react";
import type { Message } from "./types";
import ChatPanel from "./components/ChatPanel";
import GraphPanel from "./components/GraphPanel";
import GraphSidebar from "./components/GraphSidebar";
import "./App.css";

export default function App() {
  const [currentGraph, setCurrentGraph] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [chatKey, setChatKey] = useState(0);
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([]);
  const [refreshSignal, setRefreshSignal] = useState(0);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Mensagens persistidas por graphId — sobrevivem à troca de grafo
  const [messageStore, setMessageStore] = useState<Record<string, Message[]>>(
    {},
  );

  const handleSaveMessages = useCallback((graphId: string, msgs: Message[]) => {
    setMessageStore((prev) => ({ ...prev, [graphId]: msgs }));
  }, []);

  const handleAccessedNodes = useCallback((nodeIds: string[]) => {
    setHighlightedNodeIds(nodeIds);
    setTimeout(() => setHighlightedNodeIds([]), 12000);
  }, []);

  const handleMessageComplete = useCallback(() => {
    setRefreshSignal((s) => s + 1);
  }, []);

  const handleSelectGraph = useCallback((id: string, name: string) => {
    setCurrentGraph({ id, name });
    setHighlightedNodeIds([]);
    setChatKey((k) => k + 1);
  }, []);

  const handleNewGraph = useCallback(() => {
    setCurrentGraph(null);
    setHighlightedNodeIds([]);
    setChatKey((k) => k + 1);
    // Limpa histórico do estado "sem grafo" para novo chat começar do zero
    setMessageStore((prev) => {
      const next = { ...prev };
      delete next[""];
      return next;
    });
  }, []);

  const handleGraphCreated = useCallback((graphId: string, name: string) => {
    setCurrentGraph({ id: graphId, name });
    setHighlightedNodeIds([]);
    // Sem chatKey++ — o ChatPanel continua montado, preservando a conversa
    setSidebarRefresh((s) => s + 1);
    setRefreshSignal((s) => s + 1);
  }, []);

  return (
    <div className="app">
      <GraphSidebar
        currentGraphId={currentGraph?.id ?? null}
        onSelectGraph={handleSelectGraph}
        onNewGraph={handleNewGraph}
        refreshSignal={sidebarRefresh}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <header className="app-topbar">
        <button
          className="topbar-graphs-btn"
          onClick={() => setSidebarOpen((o) => !o)}
        >
          ◈ {currentGraph ? currentGraph.name : "Grafos"}
        </button>
        <span className="topbar-title">RE Expert Agent</span>
      </header>

      <main className="app-main">
        <div className="panel chat-section">
          <ChatPanel
            key={chatKey}
            graphId={currentGraph?.id ?? ""}
            initialMessages={messageStore[currentGraph?.id ?? ""]}
            onMessagesChange={handleSaveMessages}
            onAccessedNodes={handleAccessedNodes}
            onMessageComplete={handleMessageComplete}
            onGraphCreated={handleGraphCreated}
          />
        </div>

        <div className="resizer" />

        <div className="panel graph-section">
          {currentGraph ? (
            <GraphPanel
              graphId={currentGraph.id}
              highlightedNodeIds={highlightedNodeIds}
              refreshSignal={refreshSignal}
            />
          ) : (
            <div className="graph-empty-state">
              <span className="graph-empty-icon">◈</span>
              <p className="graph-empty-title">Nenhum grafo selecionado</p>
              <p className="graph-empty-sub">
                Clique em ◈ no canto superior esquerdo para escolher ou criar um
                grafo
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

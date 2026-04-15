import { useState, useCallback } from "react";
import ChatPanel from "./components/ChatPanel";
import GraphPanel from "./components/GraphPanel";
import "./App.css";

export default function App() {
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([]);

  const handleAccessedNodes = useCallback((nodeIds: string[]) => {
    setHighlightedNodeIds(nodeIds);
    // Remove destaques após 12 segundos
    setTimeout(() => setHighlightedNodeIds([]), 12000);
  }, []);

  return (
    <div className="app">
      <main className="app-main">
        <div className="panel chat-section">
          <div className="panel-label">Chat</div>
          <ChatPanel onAccessedNodes={handleAccessedNodes} />
        </div>

        <div className="resizer" />

        <div className="panel graph-section">
          <div className="panel-label">Grafo de Conhecimento</div>
          <GraphPanel highlightedNodeIds={highlightedNodeIds} />
        </div>
      </main>
    </div>
  );
}

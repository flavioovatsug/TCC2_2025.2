import { useEffect, useState } from "react";
import type { GraphMeta } from "../types";
import { fetchGraphs } from "../api";
import "./GraphSidebar.css";

interface Props {
  currentGraphId: string | null;
  onSelectGraph: (id: string, name: string) => void;
  onNewGraph: () => void;
  refreshSignal?: number;
  open: boolean;
  onClose: () => void;
}

export default function GraphSidebar({
  currentGraphId,
  onSelectGraph,
  onNewGraph,
  refreshSignal,
  open,
  onClose,
}: Props) {
  const [graphs, setGraphs] = useState<GraphMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchGraphs()
      .then(setGraphs)
      .finally(() => setLoading(false));
  }, [refreshSignal]);

  if (!open) return null;

  return (
    <>
      <div className="sb-backdrop" onClick={onClose} />
      <aside className="graph-sidebar">
        <div className="sb-header">
          <span className="sb-logo">◈</span>
          <span className="sb-title">RE Agent</span>
          <button
            className="sb-close-btn"
            onClick={onClose}
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>

        <div className="sb-section-label">Grafos</div>

        <div className="sb-list">
          {loading && (
            <div className="sb-state">
              <div className="sb-spinner" />
            </div>
          )}

          {!loading && graphs.length === 0 && (
            <div className="sb-state sb-state-empty">
              <p>Nenhum grafo ainda</p>
            </div>
          )}

          {graphs.map((g) => (
            <button
              key={g.graph_id}
              className={`sb-item ${currentGraphId === g.graph_id ? "sb-item-active" : ""}`}
              onClick={() => {
                onSelectGraph(g.graph_id, g.name);
                onClose();
              }}
              title={g.graph_id}
            >
              <span className="sb-item-icon">◈</span>
              <span className="sb-item-info">
                <span className="sb-item-name">{g.name}</span>
                <span className="sb-item-count">{g.node_count} nós</span>
              </span>
            </button>
          ))}
        </div>

        <div className="sb-footer">
          <button
            className="sb-new-btn"
            onClick={() => {
              onNewGraph();
              onClose();
            }}
          >
            + Novo Grafo
          </button>
        </div>
      </aside>
    </>
  );
}

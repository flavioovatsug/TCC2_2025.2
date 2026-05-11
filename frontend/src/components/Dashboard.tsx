import { useEffect, useState } from "react";
import type { GraphMeta } from "../types";
import { fetchGraphs, createGraph } from "../api";
import "./Dashboard.css";

interface Props {
  onOpenGraph: (graphId: string, name: string) => void;
}

export default function Dashboard({ onOpenGraph }: Props) {
  const [graphs, setGraphs] = useState<GraphMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchGraphs()
      .then(setGraphs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!newName.trim() || creating) return;
    setCreating(true);
    try {
      const g = await createGraph(newName.trim());
      onOpenGraph(g.graph_id, g.name);
    } catch (e) {
      setError((e as Error).message);
      setCreating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleCreate();
    if (e.key === "Escape") setShowModal(false);
  };

  return (
    <div className="dashboard">
      <div className="db-header">
        <div className="db-title">
          <span className="db-logo">◈</span>
          <div>
            <h1>RE Expert Agent</h1>
            <p>Grafos de Conhecimento em Engenharia de Requisitos</p>
          </div>
        </div>
        <button className="db-new-btn" onClick={() => setShowModal(true)}>
          + Novo Grafo
        </button>
      </div>

      <div className="db-section-label">Grafos disponíveis</div>

      {loading && (
        <div className="db-state">
          <div className="db-spinner" />
          <p>Carregando grafos...</p>
        </div>
      )}

      {error && (
        <div className="db-state db-state-error">
          <p>⚠ {error}</p>
          <p style={{ fontSize: 12, color: "#666", marginTop: 6 }}>
            Verifique se o servidor está rodando em localhost:8000
          </p>
        </div>
      )}

      {!loading && !error && graphs.length === 0 && (
        <div className="db-state">
          <p style={{ fontSize: 32, marginBottom: 8 }}>◈</p>
          <p>Nenhum grafo encontrado.</p>
          <p style={{ fontSize: 13, color: "#555", marginTop: 4 }}>
            Crie um novo grafo para começar.
          </p>
        </div>
      )}

      <div className="db-grid">
        {graphs.map((g) => (
          <div key={g.graph_id} className="db-card">
            <div className="db-card-icon">◈</div>
            <div className="db-card-info">
              <h3>{g.name}</h3>
              <p className="db-card-id">{g.graph_id}</p>
              <p className="db-card-count">
                {g.node_count} {g.node_count === 1 ? "nó" : "nós"}
              </p>
            </div>
            <button
              className="db-open-btn"
              onClick={() => onOpenGraph(g.graph_id, g.name)}
            >
              Abrir →
            </button>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="db-overlay" onClick={() => setShowModal(false)}>
          <div className="db-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Novo Grafo</h2>
            <p>
              Crie um grafo vazio e use o chat para adicionar requisitos com o
              agente de IA.
            </p>
            <input
              className="db-input"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ex: Sistema de Login"
              autoFocus
              maxLength={60}
            />
            <div className="db-modal-actions">
              <button
                className="db-cancel-btn"
                onClick={() => setShowModal(false)}
              >
                Cancelar
              </button>
              <button
                className="db-confirm-btn"
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
              >
                {creating ? "Criando..." : "Criar Grafo"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

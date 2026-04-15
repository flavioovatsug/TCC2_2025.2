import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphData, GraphNode, GraphLink } from "../types";
import { fetchGraph } from "../api";
import "./GraphPanel.css";

interface Props {
  highlightedNodeIds: string[];
}

const NODE_COLORS: Record<string, string> = {
  Requirement: "#4f8ef7",
  Technique: "#2ecc71",
  Instruction: "#f39c12",
  Concept: "#9b59b6",
};

const NODE_SIZES: Record<string, number> = {
  Requirement: 4,
  Technique: 8,
  Instruction: 7,
  Concept: 7,
};

const LINK_COLORS: Record<string, string> = {
  SIMILAR_TO: "rgba(79, 142, 247, 0.15)",
  USES_TECHNIQUE: "rgba(46, 204, 113, 0.5)",
  IS_A: "rgba(155, 89, 182, 0.5)",
  IS_RELATED_TO: "rgba(155, 89, 182, 0.4)",
  SUPPORTED_BY: "rgba(243, 156, 18, 0.5)",
  APPLIES_TO: "rgba(46, 204, 113, 0.4)",
  ELICITED_BY: "rgba(46, 204, 113, 0.4)",
  FOLLOWS: "rgba(243, 156, 18, 0.4)",
  REFERS_TO: "rgba(155, 89, 182, 0.4)",
  SUGGESTS_TECHNIQUE: "rgba(46, 204, 113, 0.4)",
};

type FilterState = Record<string, boolean>;

export default function GraphPanel({ highlightedNodeIds }: Props) {
  const [graphData, setGraphData] = useState<GraphData>({
    nodes: [],
    links: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    Requirement: true,
    Technique: true,
    Instruction: true,
    Concept: true,
    SIMILAR_TO: false,
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 500 });
  const highlightSet = useMemo(
    () => new Set(highlightedNodeIds),
    [highlightedNodeIds],
  );

  // Load graph data
  useEffect(() => {
    fetchGraph(200)
      .then((data) => {
        setGraphData(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height: height - 120 }); // leave room for footer
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Filtered graph (memoized)
  const filteredData = useMemo(() => {
    const visibleNodeIds = new Set(
      graphData.nodes
        .filter((n) => filters[n.label] !== false)
        .map((n) => n.id),
    );
    return {
      nodes: graphData.nodes.filter((n) => filters[n.label] !== false),
      links: graphData.links.filter((l) => {
        const srcId =
          typeof l.source === "string" ? l.source : (l.source as GraphNode).id;
        const tgtId =
          typeof l.target === "string" ? l.target : (l.target as GraphNode).id;
        if (!visibleNodeIds.has(srcId) || !visibleNodeIds.has(tgtId))
          return false;
        if (l.type === "SIMILAR_TO") return filters.SIMILAR_TO;
        return true;
      }),
    };
  }, [graphData, filters]);

  const paintNode = useCallback(
    (node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const baseR = NODE_SIZES[node.label] ?? 5;
      const isHighlighted = highlightSet.has(node.id);
      const r = isHighlighted ? baseR * 1.9 : baseR;
      const color = NODE_COLORS[node.label] ?? "#ccc";

      // Glow for highlighted
      if (isHighlighted) {
        const gradient = ctx.createRadialGradient(x, y, r, x, y, r * 3);
        gradient.addColorStop(0, color + "88");
        gradient.addColorStop(1, "rgba(0,0,0,0)");
        ctx.beginPath();
        ctx.arc(x, y, r * 3, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      // White border for highlighted or non-Requirement
      if (isHighlighted) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      } else if (node.label !== "Requirement") {
        ctx.strokeStyle = "rgba(255,255,255,0.3)";
        ctx.lineWidth = 1 / globalScale;
        ctx.stroke();
      }

      // Labels for non-Requirement nodes, or highlighted ones
      const showLabel = node.label !== "Requirement" || isHighlighted;
      if (showLabel) {
        const fontSize = Math.max(10 / globalScale, isHighlighted ? 5 : 4);
        ctx.font = `${isHighlighted ? "bold " : ""}${fontSize}px Sans-Serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = isHighlighted ? "#ffffff" : "rgba(255,255,255,0.8)";
        const label = node.name || node.id;
        ctx.fillText(
          label.length > 30 ? label.slice(0, 28) + "…" : label,
          x,
          y + r + 2 / globalScale,
        );
      }
    },
    [highlightSet],
  );

  const linkColor = useCallback((link: GraphLink) => {
    return LINK_COLORS[link.type] ?? "rgba(100,100,100,0.3)";
  }, []);

  const linkWidth = useCallback(
    (link: GraphLink) => {
      if (link.type === "SIMILAR_TO") return 0.5;
      const src =
        typeof link.source === "string"
          ? link.source
          : (link.source as GraphNode).id;
      const tgt =
        typeof link.target === "string"
          ? link.target
          : (link.target as GraphNode).id;
      return highlightSet.has(src) || highlightSet.has(tgt) ? 2 : 1;
    },
    [highlightSet],
  );

  const handleNodeClick = useCallback((node: unknown) => {
    setSelectedNode(node as GraphNode);
  }, []);

  const toggleFilter = (key: string) => {
    setFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (loading) {
    return (
      <div className="graph-panel graph-loading">
        <div className="spinner" />
        <p>Carregando grafo...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="graph-panel graph-error">
        <p>Erro ao carregar grafo: {error}</p>
        <p>Verifique se o Neo4j está rodando e o backend está ativo.</p>
      </div>
    );
  }

  if (graphData.nodes.length === 0) {
    return (
      <div className="graph-panel graph-error">
        <p style={{ fontSize: 32, marginBottom: 8 }}>◈</p>
        <p style={{ color: "#ccc", marginBottom: 6 }}>Grafo vazio</p>
        <p style={{ fontSize: 12, textAlign: "center", maxWidth: 340 }}>
          O Neo4j está conectado mas sem dados.
          <br />
          Execute o script para popular o grafo:
        </p>
        <code
          style={{
            background: "#1a1a1a",
            padding: "8px 14px",
            borderRadius: 6,
            fontSize: 12,
            marginTop: 10,
            color: "#4f8ef7",
          }}
        >
          python Knowledge_Graphs/graph_creator.py
        </code>
      </div>
    );
  }

  return (
    <div className="graph-panel" ref={containerRef}>
      {/* Toolbar */}
      <div className="graph-toolbar">
        <span className="graph-stats">
          {filteredData.nodes.length} nós · {filteredData.links.length} arestas
          {highlightedNodeIds.length > 0 && (
            <span className="highlight-badge">
              {" "}
              · {highlightedNodeIds.length} destacados
            </span>
          )}
        </span>
        <div className="filter-buttons">
          {["Requirement", "Technique", "Instruction", "Concept"].map(
            (type) => (
              <button
                key={type}
                className={`filter-btn ${filters[type] ? "active" : ""}`}
                style={{ "--color": NODE_COLORS[type] } as React.CSSProperties}
                onClick={() => toggleFilter(type)}
              >
                {type.slice(0, 3)}
              </button>
            ),
          )}
          <button
            className={`filter-btn ${filters.SIMILAR_TO ? "active" : ""}`}
            style={{ "--color": "#4f8ef7" } as React.CSSProperties}
            onClick={() => toggleFilter("SIMILAR_TO")}
            title="Mostrar arestas SIMILAR_TO"
          >
            ~
          </button>
        </div>
      </div>

      {/* Force Graph */}
      <ForceGraph2D
        graphData={filteredData as any}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0a0a0f"
        nodeId="id"
        nodeLabel={(n: any) => `[${n.label}] ${n.name || n.id}`}
        nodeCanvasObject={paintNode as any}
        nodePointerAreaPaint={(node: any, color, ctx) => {
          const r = (NODE_SIZES[node.label] ?? 5) * 2;
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkColor={linkColor as any}
        linkWidth={linkWidth as any}
        linkDirectionalArrowLength={(l: any) =>
          l.type !== "SIMILAR_TO" ? 3 : 0
        }
        linkDirectionalArrowRelPos={1}
        onNodeClick={handleNodeClick}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        cooldownTicks={200}
      />

      {/* Node detail panel */}
      {selectedNode && (
        <div className="node-detail">
          <div className="node-detail-header">
            <span
              className="node-type-badge"
              style={{ background: NODE_COLORS[selectedNode.label] }}
            >
              {selectedNode.label}
            </span>
            <strong>{selectedNode.id}</strong>
            {selectedNode.communityId !== undefined &&
              selectedNode.communityId !== null && (
                <span className="community-badge">
                  Comunidade {selectedNode.communityId}
                </span>
              )}
            <button className="close-btn" onClick={() => setSelectedNode(null)}>
              ✕
            </button>
          </div>
          <p className="node-detail-text">
            {selectedNode.text || selectedNode.name}
          </p>
          {selectedNode.summary && (
            <p className="node-detail-summary">
              <em>Critérios:</em> {selectedNode.summary}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

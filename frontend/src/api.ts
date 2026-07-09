import type { GraphData, GraphMeta, SSEEvent } from "./types";

const API_URL = import.meta.env.PROD ? "https://tcc-back-7x28.onrender.com" : "";
const WS_BASE = import.meta.env.PROD 
  ? "wss://tcc-back-7x28.onrender.com/ws/chat" 
  : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/chat`;

export async function fetchGraph(
  limit = 200,
  graphId = "default",
): Promise<GraphData> {
  const res = await fetch(`${API_URL}/api/graph?limit=${limit}&graph_id=${graphId}`);
  if (!res.ok) throw new Error(`Graph API error: ${res.status}`);
  return res.json();
}

export async function fetchGraphs(): Promise<GraphMeta[]> {
  const res = await fetch(`${API_URL}/api/graphs");
  if (!res.ok) throw new Error(`Graphs API error: ${res.status}`);
  return res.json();
}

export async function createGraph(
  name: string,
): Promise<GraphMeta & { graph_id: string }> {
  const res = await fetch(`${API_URL}/api/graphs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Create graph error: ${res.status}`);
  return res.json();
}

export async function* streamChat(
  question: string,
  graphId = "default",
): AsyncGenerator<SSEEvent> {
  const ws = new WebSocket(WS_BASE);
  const queue: SSEEvent[] = [];
  let waiting: ((e: SSEEvent) => void) | null = null;

  const push = (event: SSEEvent) => {
    if (waiting) {
      const fn = waiting;
      waiting = null;
      fn(event);
    } else {
      queue.push(event);
    }
  };

  try {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("WebSocket timeout")),
        5000,
      );
      ws.onopen = () => {
        clearTimeout(timer);
        resolve();
      };
      ws.onerror = () => {
        clearTimeout(timer);
        reject(new Error("Falha ao conectar ao servidor"));
      };
    });
  } catch (e) {
    yield { type: "error", content: (e as Error).message };
    return;
  }

  ws.onmessage = (e) => {
    try {
      push(JSON.parse(e.data) as SSEEvent);
    } catch {
      // ignora mensagem malformada
    }
  };
  ws.onerror = () => push({ type: "error", content: "WebSocket error" });
  ws.onclose = (e) => {
    if (!e.wasClean) push({ type: "done" });
  };

  ws.send(JSON.stringify({ type: "chat", question, graph_id: graphId }));

  const next = (): Promise<SSEEvent> => {
    if (queue.length > 0) return Promise.resolve(queue.shift()!);
    return new Promise((resolve) => {
      waiting = resolve;
    });
  };

  try {
    while (true) {
      const event = await next();
      yield event;
      if (event.type === "done" || event.type === "error") break;
    }
  } finally {
    if (
      ws.readyState === WebSocket.OPEN ||
      ws.readyState === WebSocket.CONNECTING
    ) {
      ws.close();
    }
  }
}

export interface GraphNode {
  id: string;
  label: "Requirement" | "Technique" | "Instruction" | "Concept";
  name: string;
  text?: string;
  summary?: string;
  communityId?: number;
  category?: string;
  context?: string;
  // runtime
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
  __highlighted?: boolean;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export type MessageRole = "user" | "agent";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  isStreaming?: boolean;
}

export type SSEEvent =
  | { type: "thinking"; content: string }
  | { type: "token"; content: string }
  | { type: "accessed_nodes"; node_ids: string[] }
  | { type: "error"; content: string }
  | { type: "done" };

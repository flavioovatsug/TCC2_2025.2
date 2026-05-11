import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import type { Message } from "../types";
import { streamChat } from "../api";
import "./ChatPanel.css";

interface Props {
  onAccessedNodes: (nodeIds: string[]) => void;
  graphId: string;
  initialMessages?: Message[];
  onMessagesChange?: (graphId: string, messages: Message[]) => void;
  onMessageComplete?: () => void;
  onGraphCreated?: (graphId: string, name: string) => void;
}

export default function ChatPanel({
  onAccessedNodes,
  graphId,
  initialMessages,
  onMessagesChange,
  onMessageComplete,
  onGraphCreated,
}: Props) {
  const WELCOME: Message = {
    id: "welcome",
    role: "agent",
    content:
      "Olá! Sou um especialista em **Engenharia de Requisitos** com acesso ao grafo de conhecimento.\n\nPosso ajudar com:\n- Buscar requisitos específicos\n- Explicar técnicas de elicitação\n- Analisar padrões nos requisitos\n- Explicar conceitos de ER\n\nO que deseja saber?",
  };
  const [messages, setMessages] = useState<Message[]>(
    initialMessages && initialMessages.length > 0 ? initialMessages : [WELCOME],
  );
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [progress, setProgress] = useState<{
    message: string;
    percent: number;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Persiste mensagens no store do pai sempre que atualizam
  useEffect(() => {
    onMessagesChange?.(graphId, messages);
  }, [messages, graphId]); // eslint-disable-line react-hooks/exhaustive-deps

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const question = input.trim();
    if (!question || isStreaming) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };
    const agentMsgId = (Date.now() + 1).toString();
    const agentMsg: Message = {
      id: agentMsgId,
      role: "agent",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, agentMsg]);
    setInput("");
    setIsStreaming(true);

    try {
      for await (const event of streamChat(question, graphId)) {
        console.log(`[chat] event:${event.type}`, event);
        if (event.type === "thinking") {
          // já mostrado pelo indicador dentro da bolha
        } else if (event.type === "progress") {
          console.log(`[chat] progress: ${event.percent}% — ${event.message}`);
          setProgress({ message: event.message, percent: event.percent });
        } else if (event.type === "graph_created") {
          console.log(
            `[chat] graph_created: id=${event.graph_id} name=${event.name} nodes=${event.node_count}`,
          );
          setProgress(null);
          // Navega para o novo grafo após breve delay para mostrar a resposta
          setTimeout(() => onGraphCreated?.(event.graph_id, event.name), 1200);
        } else if (event.type === "accessed_nodes") {
          console.log(`[chat] accessed_nodes: ${event.node_ids?.length} nodes`);
          onAccessedNodes(event.node_ids);
        } else if (event.type === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentMsgId
                ? { ...m, content: m.content + event.content }
                : m,
            ),
          );
        } else if (event.type === "error") {
          // Limpa mensagens de erro técnicas do LiteLLM/OpenRouter
          let errMsg = event.content;
          if (
            errMsg.includes("RateLimitError") ||
            errMsg.includes("rate-limited") ||
            errMsg.includes("429")
          ) {
            errMsg =
              "O modelo de IA está sobrecarregado (rate limit). Aguarde alguns minutos e tente novamente.";
          } else if (
            errMsg.includes("ServiceUnavailable") ||
            errMsg.includes("Connection")
          ) {
            errMsg =
              "Não foi possível conectar ao Neo4j. Verifique se o banco de dados está rodando.";
          } else if (errMsg.length > 200) {
            errMsg = errMsg.slice(0, 200) + "...";
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentMsgId
                ? { ...m, content: `⚠️ ${errMsg}`, isStreaming: false }
                : m,
            ),
          );
        } else if (event.type === "done") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentMsgId ? { ...m, isStreaming: false } : m,
            ),
          );
        }
      }
    } finally {
      setIsStreaming(false);
      setProgress(null);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentMsgId ? { ...m, isStreaming: false } : m,
        ),
      );
      onMessageComplete?.();
    }
  }, [
    input,
    isStreaming,
    onAccessedNodes,
    graphId,
    onMessageComplete,
    onGraphCreated,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-panel">
      {/* Toast de progresso — criação de grafo */}
      {progress && (
        <div className="progress-toast">
          <div className="progress-toast-header">
            <span className="progress-toast-icon">◈</span>
            <span className="progress-toast-label">Criando grafo...</span>
            <span className="progress-toast-pct">{progress.percent}%</span>
          </div>
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          <p className="progress-toast-msg">{progress.message}</p>
        </div>
      )}

      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            {msg.role === "agent" && <div className="message-avatar">RE</div>}
            <div className="message-bubble">
              {msg.role === "agent" ? (
                msg.isStreaming && !msg.content ? (
                  <div className="thinking">
                    <span className="dot" />
                    <span className="dot" />
                    <span className="dot" />
                  </div>
                ) : (
                  <>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                    {msg.isStreaming && <span className="cursor-blink" />}
                  </>
                )
              ) : (
                <p>{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Pergunte sobre engenharia de requisitos... (Enter para enviar)"
          rows={3}
          disabled={isStreaming}
        />
        <button
          className="send-button"
          onClick={sendMessage}
          disabled={isStreaming || !input.trim()}
        >
          {isStreaming ? "⏳" : "➤"}
        </button>
      </div>
    </div>
  );
}

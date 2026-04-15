import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import type { Message } from "../types";
import { streamChat } from "../api";
import "./ChatPanel.css";

interface Props {
  onAccessedNodes: (nodeIds: string[]) => void;
}

export default function ChatPanel({ onAccessedNodes }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "agent",
      content:
        "Olá! Sou um especialista em **Engenharia de Requisitos** com acesso ao grafo de conhecimento.\n\nPosso ajudar com:\n- Buscar requisitos específicos\n- Explicar técnicas de elicitação\n- Analisar padrões nos requisitos\n- Explicar conceitos de ER\n\nO que deseja saber?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
      for await (const event of streamChat(question)) {
        if (event.type === "thinking") {
          // já mostrado pelo indicador dentro da bolha
        } else if (event.type === "accessed_nodes") {
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
      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentMsgId ? { ...m, isStreaming: false } : m,
        ),
      );
    }
  }, [input, isStreaming, onAccessedNodes]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-panel">
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

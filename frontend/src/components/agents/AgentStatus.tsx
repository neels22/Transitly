import { useState, useEffect, useRef } from "react";
import { X, Send, Loader2 } from "lucide-react";

interface ChecklistItem {
  id: string;
  title: string;
  status: "pending" | "agent_done" | "user_done";
  agent_label: string | null;
  detail?: string;
}

interface Message {
  id: string;
  content: string;
  sender: "user" | "ai";
  timestamp: Date;
}

interface AgentModalProps {
  userId: string;
  onClose: () => void;
}

export default function AgentStatus({ userId, onClose }: AgentModalProps) {
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      content: "Hi! I'm your moving assistant. Starting automation...",
      sender: "ai",
      timestamp: new Date(),
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");
  const [isRunning, setIsRunning] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const token = localStorage.getItem("id_token");
    if (!token) {
      addAIMessage("Error: Not authenticated. Please sign in.");
      setIsRunning(false);
      return;
    }
  
    const apiUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const url = `${apiUrl}/run-agents-stream`;
  
    // Add abort controller to cancel the connection
    const abortController = new AbortController();
    let isActive = true;
  
    const connectSSE = async () => {
      try {
        const response = await fetch(url, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "text/event-stream",
          },
          signal: abortController.signal, // Add abort signal
        });
  
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
  
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
  
        if (!reader) {
          throw new Error("Failed to get response reader");
        }
  
        while (true) {
          if (!isActive) { // Check if we should stop
            reader.cancel();
            break;
          }
  
          const { done, value } = await reader.read();
          if (done) break;
  
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");
  
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (isActive) { // Only process if still active
                  handleSSEMessage(data);
                }
              } catch (e) {
                console.error("Failed to parse SSE data:", e);
              }
            }
          }
        }
      } catch (error) {
        // Ignore abort errors (they're expected on cleanup)
        if (error instanceof Error && error.name === 'AbortError') {
          console.log("SSE connection aborted (expected on cleanup)");
          return;
        }
        
        if (isActive) { // Only show error if not intentionally aborted
          console.error("SSE Connection error:", error);
          addAIMessage("Connection error. Please try again.");
          setIsRunning(false);
        }
      }
    };
  
    connectSSE();
  
    // Cleanup function - runs when component unmounts or dependencies change
    return () => {
      isActive = false;
      abortController.abort();
      console.log("SSE cleanup: connection aborted");
    };
  }, [userId]);
  
  const handleSSEMessage = (data: any) => {
    switch (data.type) {
      case "connected":
        addAIMessage(data.message);
        break;

      case "user_details":
        addAIMessage("✓ Loaded your move details!");
        break;

      case "checklist":
        const newChecklist = data.data.map((item: any, idx: number) => ({
          id: String(idx + 1),
          title: item.title,
          status: item.status === "done" ? "agent_done" : "pending",
          agent_label: item.agent_label,
          detail: item.detail || "",
        }));
        setChecklist(newChecklist);
        addAIMessage(
          `✓ Generated your moving checklist with ${newChecklist.length} tasks!`
        );
        break;

      case "agent_start":
        addAIMessage(`🔄 ${data.name || data.agent}...`);
        break;

      case "agent_complete":
        addAIMessage(`✓ Completed: ${data.name || data.agent}`);
        updateChecklistStatus(data.agent, "agent_done");
        break;

      case "complete":
        addAIMessage("🎉 All automation tasks completed!");
        if (data.data?.address_change_result?.success) {
          addAIMessage("✓ Amazon address successfully updated!");
        }
        setIsRunning(false);
        break;

      case "error":
        addAIMessage(`❌ Error: ${data.message}`);
        setIsRunning(false);
        break;
    }
  };

  const addAIMessage = (content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        content,
        sender: "ai",
        timestamp: new Date(),
      },
    ]);
  };

  const updateChecklistStatus = (
    agentLabel: string,
    status: ChecklistItem["status"]
  ) => {
    setChecklist((prev) =>
      prev.map((item) =>
        item.agent_label === agentLabel ? { ...item, status } : item
      )
    );
  };

  const toggleChecklistItem = (id: string) => {
    setChecklist((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              status: item.status === "user_done" ? "pending" : "user_done",
            }
          : item
      )
    );
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      content: inputMessage,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setInputMessage("");

    try {
      const token = localStorage.getItem("id_token");
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: inputMessage,
            checklist_context: checklist.map((item) => ({
              title: item.title,
              status: item.status,
              agent_label: item.agent_label,
            })),
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to send message");
      }

      const data = await response.json();

      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        content: data.message,
        sender: "ai",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content:
          "Sorry, I'm having trouble responding right now. Please try again.",
        sender: "ai",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const getStrikethroughStyle = (status: ChecklistItem["status"]) => {
    if (status === "agent_done") {
      return "line-through decoration-red-500 decoration-2";
    }
    if (status === "user_done") {
      return "line-through decoration-blue-500 decoration-2";
    }
    return "";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-2xl w-[90vw] h-[85vh] max-w-7xl flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-gray-900">
              Moving Assistant
            </h2>
            {isRunning && (
              <Loader2 className="w-5 h-5 text-[#FF4124] animate-spin" />
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 transition"
          >
            <X size={24} />
          </button>
        </div>

        {/* Main Content - Split View */}
        <div className="flex flex-1 overflow-hidden">
          {/* LEFT: Checklist */}
          <div className="w-1/2 border-r border-gray-200 p-6 overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4 text-gray-900">
              Tasks Checklist
            </h3>

            {checklist.length === 0 ? (
              <div className="flex items-center justify-center h-40 text-gray-400">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                  <p>Generating your checklist...</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {checklist.map((item) => (
                  <label
                    key={item.id}
                    className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition group"
                  >
                    <input
                      type="checkbox"
                      checked={item.status !== "pending"}
                      onChange={() => toggleChecklistItem(item.id)}
                      className="mt-1 w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-2 focus:ring-blue-500 cursor-pointer"
                    />
                    <div className="flex-1">
                      <div
                        className={`text-sm font-medium text-gray-900 ${getStrikethroughStyle(
                          item.status
                        )}`}
                      >
                        {item.title}
                      </div>
                      {item.detail && (
                        <div className="text-xs text-gray-500 mt-1">
                          {item.detail}
                        </div>
                      )}
                      {item.status !== "pending" && (
                        <div className="text-xs text-gray-500 mt-1">
                          {item.status === "agent_done"
                            ? "✓ Completed by AI"
                            : "✓ Manually completed"}
                        </div>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* RIGHT: Chat */}
          <div className="w-1/2 flex flex-col bg-gray-50">
            {/* Chat Header */}
            <div className="px-6 py-4 border-b border-gray-200 bg-white">
              <h3 className="text-lg font-semibold text-gray-900">
                Activity Log
              </h3>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-2 ${
                      message.sender === "user"
                        ? "bg-[#FF4124] text-white"
                        : "bg-white text-gray-900 border border-gray-200"
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">
                      {message.content}
                    </p>
                    <p
                      className={`text-xs mt-1 ${
                        message.sender === "user"
                          ? "text-white/70"
                          : "text-gray-500"
                      }`}
                    >
                      {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input */}
            <div className="p-4 bg-white border-t border-gray-200">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
                  placeholder="Ask a question... (coming soon)"
                  disabled={true}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#FF4124] focus:border-transparent text-sm disabled:bg-gray-50 disabled:cursor-not-allowed"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim()}
                  className="bg-[#FF4124] text-white rounded-full p-2 hover:bg-black transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send size={20} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

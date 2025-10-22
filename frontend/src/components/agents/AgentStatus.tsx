import { useState, useEffect, useRef } from "react";
import { X, Send, Loader2 } from "lucide-react";

interface ChecklistItem {
  id: string;
  title: string;
  status: "todo" | "agentdone" | "manualdone";
  agent_label: string | null;
  detail?: string;
  checklistId?: string;
  moveId?: string;
}

interface Message {
  id: string;
  content: string;
  sender: "user" | "ai";
  timestamp: Date;
}

interface HistoricalChecklistItem {
  title: string;
  status: string; // 'todo' | 'agentdone' | 'manualdone'
}

interface AgentModalProps {
  userId: string;
  onClose: () => void;
  initialChecklist?: HistoricalChecklistItem[]; // when opening from a saved card
  startStream?: boolean; // whether to start SSE run (default true)
}

export default function AgentStatus({ userId, onClose, initialChecklist, startStream = true }: AgentModalProps) {
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [savingItems, setSavingItems] = useState<Set<string>>(new Set());
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
    // If we're opening a historical card, preload the checklist and skip SSE
    if (!startStream) {
      const mapped: ChecklistItem[] = (initialChecklist || []).map((item, idx) => ({
        id: String(idx + 1),
        title: item.title,
        status:
          item.status === "agentdone"
            ? "agentdone"
            : item.status === "manualdone"
            ? "manualdone"
            : "todo",
        agent_label: item.agent_label || null,
        detail: item.detail || "",
        checklistId: item.checklistId, // Use the real checklistId from backend
      }));
      setChecklist(mapped);
      setIsRunning(false);
      return;
    }

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
  }, [userId, startStream]);
  
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
          status: item.status === "done" ? "agentdone" : "todo",
          agent_label: item.agent_label,
          detail: item.detail || "",
          checklistId: `temp#cl${idx + 1}`, // Temporary ID until saved to backend
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
        updateChecklistStatus(data.agent, "agentdone");
        break;

      case "complete":
        addAIMessage("🎉 All automation tasks completed!");
        if (data.data?.address_change_result?.success) {
          addAIMessage("✓ Amazon address successfully updated!");
        }
        setIsRunning(false);
        // Automatically save checklist when all tasks are completed
        // Use checklist data from the completion message if available
        if (data.data?.checklist && data.data.checklist.length > 0) {
          console.log("[AgentModal] Using checklist from completion message:", data.data.checklist);
          handleChecklistSaveWithData(data.data.checklist);
        } else {
          // Fallback to using state checklist
          setTimeout(() => {
            handleChecklistSave();
          }, 100);
        }
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

  const toggleChecklistItem = async (id: string) => {
    // Mark this item as saving
    setSavingItems(prev => new Set(prev).add(id));
    
    // Find the current item to get its checklistId
    const currentItem = checklist.find(item => item.id === id);
    if (!currentItem) {
      console.error("Item not found:", id);
      setSavingItems(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
      return;
    }
    
    // Determine new status
    const newStatus = currentItem.status === "manualdone" ? "todo" : "manualdone";
    
    // Update local state immediately for better UX
    setChecklist((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              status: newStatus,
            }
          : item
      )
    );
    
    try {
      const token = localStorage.getItem("id_token");
      if (!token) {
        console.error("No authentication token found");
        addAIMessage("❌ Authentication error. Please sign in again.");
        return;
      }

      // Use the checklistId from the item, or show error if not present
      if (!currentItem.checklistId) {
        console.error("No checklistId found for item:", currentItem);
        addAIMessage("❌ Cannot update item - missing checklist ID. This item needs to be saved first.");
        return;
      }
      
      console.log(`[AgentModal] Updating checklist item ${currentItem.checklistId} to status: ${newStatus}`);

      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/update-checklist-status`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            checklist_id: currentItem.checklistId,
            status: newStatus,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to update checklist status: ${response.status}`);
      }

      const result = await response.json();
      console.log("[AgentModal] Checklist item status updated successfully:", result);
      
      // Add subtle success message
      addAIMessage(`✓ ${currentItem.title} marked as ${newStatus === "manualdone" ? "completed" : "pending"}`);
      
    } catch (error) {
      console.error("Failed to update checklist item status:", error);
      addAIMessage("❌ Failed to update status. Please try again.");
      
      // Revert the local state change on error
      setChecklist((prev) =>
        prev.map((item) =>
          item.id === id
            ? {
                ...item,
                status: currentItem.status, // Revert to original status
              }
            : item
        )
      );
    } finally {
      // Remove from saving state
      setSavingItems(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
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
    if (status === "agentdone") {
      return "line-through decoration-red-500 decoration-2";
    }
    if (status === "manualdone") {
      return "line-through decoration-blue-500 decoration-2";
    }
    return "";
  };

  // Save checklist to backend with provided data
  const handleChecklistSaveWithData = async (checklistData: any[]) => {
    try {
      const token = localStorage.getItem("id_token");
      if (!token) {
        console.error("No authentication token found");
        return;
      }

      console.log("[AgentModal] Saving checklist with provided data:", checklistData);
      
      if (checklistData.length === 0) {
        console.warn("[AgentModal] Provided checklist is empty, skipping save");
        addAIMessage("⚠️ No checklist items to save");
        return;
      }

      const items = checklistData.map((item: any, idx: number) => ({
        id: String(idx + 1),
        title: item.title,
        status: item.status === "done" ? "agentdone" : "todo",
        agent_label: item.agent_label,
        detail: item.detail || "",
      }));

      console.log("[AgentModal] Sending checklist items:", items);

      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/save-checklist`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            checklist: items,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to save checklist: ${response.status}`);
      }

      const result = await response.json();
      console.log("[AgentModal] Checklist saved successfully:", result);
      
      // Update the frontend checklist state with the checklistIds from backend
      if (result.items && result.items.length > 0) {
        const updatedChecklist = checklist.map((item, idx) => {
          const savedItem = result.items[idx];
          if (savedItem) {
            return {
              ...item,
              checklistId: savedItem.checklistId,
              moveId: savedItem.moveId || item.moveId
            };
          }
          return item;
        });
        setChecklist(updatedChecklist);
        console.log("[AgentModal] Updated frontend checklist with checklistIds:", updatedChecklist);
      }
      
      // Add success message to activity log with details
      addAIMessage(`✓ Checklist saved successfully as new record! (${result.items_saved} items)`);
      
    } catch (error) {
      console.error("[AgentModal] Failed to save checklist:", error);
      addAIMessage("❌ Failed to save checklist. Please try again.");
    }
  };

  // Save checklist to backend
  const handleChecklistSave = async () => {
    try {
      const token = localStorage.getItem("id_token");
      if (!token) {
        console.error("No authentication token found");
        return;
      }

      console.log("[AgentModal] Current checklist state:", checklist);
      
      if (checklist.length === 0) {
        console.warn("[AgentModal] Checklist is empty, skipping save");
        addAIMessage("⚠️ No checklist items to save");
        return;
      }

      const items = checklist.map((item) => ({
        id: item.id,
        title: item.title,
        status: item.status,
        agent_label: item.agent_label,
        detail: item.detail || "",
      }));

      console.log("[AgentModal] Sending checklist items:", items);

      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/save-checklist`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            checklist: items,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to save checklist: ${response.status}`);
      }

      const result = await response.json();
      console.log("[AgentModal] Checklist saved successfully:", result);
      
      // Update the frontend checklist state with the checklistIds from backend
      if (result.items && result.items.length > 0) {
        const updatedChecklist = checklist.map((item, idx) => {
          const savedItem = result.items[idx];
          if (savedItem) {
            return {
              ...item,
              checklistId: savedItem.checklistId,
              moveId: savedItem.moveId || item.moveId
            };
          }
          return item;
        });
        setChecklist(updatedChecklist);
        console.log("[AgentModal] Updated frontend checklist with checklistIds:", updatedChecklist);
      }
      
      // Add success message to activity log with details
      addAIMessage(`✓ Checklist saved successfully as new record! (${result.items_saved} items)`);
      
    } catch (error) {
      console.error("[AgentModal] Failed to save checklist:", error);
      addAIMessage("❌ Failed to save checklist. Please try again.");
    }
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
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={item.status === "manualdone" || item.status === "agentdone"}
                        onChange={() => toggleChecklistItem(item.id)}
                        disabled={savingItems.has(item.id)}
                        className="mt-1 w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-2 focus:ring-blue-500 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      />
                      {savingItems.has(item.id) && (
                        <Loader2 className="absolute -top-1 -right-1 w-3 h-3 text-blue-600 animate-spin" />
                      )}
                    </div>
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
                      {item.status !== "todo" && (
                        <div className="text-xs text-gray-500 mt-1">
                          {item.status === "agentdone"
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

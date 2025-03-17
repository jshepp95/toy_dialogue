import React, { useState, useEffect, useRef } from "react";
import { UserOutlined, RobotOutlined } from "@ant-design/icons";
import { Bubble, Sender } from "@ant-design/x";
import { Flex, type GetProp, Typography, message } from "antd";
import ComplexMessage from "./components/ComplexMessage";
import markdownit from "markdown-it";

// Initialize markdown-it
const md = markdownit({ html: true, breaks: true });

// Define the markdown renderer function
const renderMarkdown = (content: string) => (
  <Typography>
    <div dangerouslySetInnerHTML={{ __html: md.render(content) }} />
  </Typography>
);

// Define types for selected categories
interface SelectedCategory {
  buyer_category: string;
  product_category: string;
  key: string | number;
}

const roles: GetProp<typeof Bubble.List, "roles"> = {
  ai: {
    placement: "start",
    avatar: { icon: <RobotOutlined />, style: { background: "#fde3cf" } },
    typing: { step: 5, interval: 20 },
    style: { maxWidth: 800 }, // Increased max width to accommodate tables
    messageRender: (content) => (
      <ComplexMessage 
        content={content} 
        onSelectionApplied={(selected) => handleSelectionApplied(selected)}
      />
    ),
  },
  local: {
    placement: "end",
    avatar: { icon: <UserOutlined />, style: { background: "#87d068" } },
    messageRender: renderMarkdown,
  },
};

// Function to handle selection from the table
const handleSelectionApplied = (selected: SelectedCategory[]) => {
  // Format the categories for display
  const categoriesText = selected.map(
    item => `${item.buyer_category} > ${item.product_category}`
  ).join(", ");
  
  // Show success message
  message.success(`Selected ${selected.length} categories for audience building: ${categoriesText}`);
  
  // Here you would typically send this selection to your backend
  // For example:
  // sendSelectedCategoriesToBackend(selected);
};

const ChatApp = () => {
  const [content, setContent] = useState("");
  const webSocketRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<{ id: number; message: any; role: "ai" | "local" }[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(true);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    webSocketRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      setConnecting(false);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setConnecting(true);
    };

    ws.onmessage = (event) => {
      const data = event.data;
      console.log("Received message:", data);

      if (typeof data === "string" && data.startsWith("THREAD_ID:")) {
        setThreadId(data.substring(10));
        return;
      }

      // Try to parse the message as JSON, if it fails, treat it as plain text
      try {
        const jsonData = JSON.parse(data);
        if (jsonData.type === "complex") {
          setMessages((prev) => [...prev, { 
            id: prev.length, 
            message: { 
              text: jsonData.text, 
              table: jsonData.table 
            }, 
            role: "ai" 
          }]);
        } else {
          setMessages((prev) => [...prev, { id: prev.length, message: jsonData, role: "ai" }]);
        }
      } catch (e) {
        // If not JSON, treat as plain text
        setMessages((prev) => [...prev, { id: prev.length, message: data, role: "ai" }]);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const sendMessage = (message: string) => {
    if (!webSocketRef.current || webSocketRef.current.readyState !== WebSocket.OPEN) {
      console.error("WebSocket is not connected.");
      return;
    }

    setMessages((prev) => [...prev, { id: prev.length, message, role: "local" }]);
    webSocketRef.current.send(message);
  };

  // Function to send selected categories to backend
  const sendSelectedCategoriesToBackend = (categories: SelectedCategory[]) => {
    if (!webSocketRef.current || webSocketRef.current.readyState !== WebSocket.OPEN) {
      console.error("WebSocket is not connected.");
      return;
    }

    const message = {
      type: "selection",
      categories: categories
    };
    
    webSocketRef.current.send(JSON.stringify(message));
  };

  return (
    <Flex vertical gap="middle" style={{ maxWidth: 1000, margin: "0 auto", padding: 20 }}>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        {connecting ? <div>Connecting to server...</div> : <div>Connected! {threadId ? `Thread ID: ${threadId}` : ""}</div>}
      </div>

      <Bubble.List
        roles={roles}
        style={{ height: 600, overflow: "auto" }}
        items={messages.map(({ id, message, role }) => ({
          key: id,
          role,
          content: message,
        }))}
      />

      <Sender
        disabled={connecting}
        value={content}
        onChange={setContent}
        onSubmit={(nextContent) => {
          sendMessage(nextContent);
          setContent("");
        }}
        placeholder="Type your message here..."
      />
    </Flex>
  );
};

export default ChatApp;
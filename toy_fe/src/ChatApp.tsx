import React, { useState, useEffect, useRef } from "react";
import { UserOutlined, RobotOutlined } from "@ant-design/icons";
import { Bubble, Sender } from "@ant-design/x";
import { Flex, type GetProp, Typography, Table } from "antd";
import markdownit from "markdown-it";

// Initialize markdown-it
const md = markdownit({ html: true, breaks: true });

// Define the markdown renderer function
const renderMarkdown = (content: string) => (
  <Typography>
    <div dangerouslySetInnerHTML={{ __html: md.render(content) }} />
  </Typography>
);

// Define types for the table data
interface TableSku {
  name: string;
  sku: string | number;
}

interface TableRow {
  buyer_category: string;
  product_category: string;
  skus: TableSku[];
  count: number;
}

interface ProductTableData {
  query: string;
  total_results: number;
  rows: TableRow[];
}

// Define the component to render product tables
const ProductTable = ({ tableData }: { tableData: ProductTableData }) => {
  // Prepare columns for Ant Design Table
  const columns = [
    {
      title: 'Buyer Category',
      dataIndex: 'buyer_category',
      key: 'buyer_category',
    },
    {
      title: 'Product Category',
      dataIndex: 'product_category',
      key: 'product_category',
    },
    {
      title: 'Sample SKUs',
      dataIndex: 'skus',
      key: 'skus',
      render: (skus: TableSku[]) => (
        <ul style={{ paddingLeft: '20px', margin: 0 }}>
          {skus.map((sku, index) => (
            <li key={index}>{sku.name} (SKU: {sku.sku})</li>
          ))}
        </ul>
      ),
    },
    {
      title: 'Total SKUs',
      dataIndex: 'count',
      key: 'count',
    },
  ];

  return (
    <Table 
      dataSource={tableData.rows.map((row, index) => ({ ...row, key: index }))} 
      columns={columns} 
      pagination={false}
      size="small"
      style={{ marginTop: '10px', marginBottom: '10px' }}
    />
  );
};

// Define types for message content
type MessageContent = string | {
  text: string;
  table: ProductTableData;
};

// Define custom message component to handle complex messages
const ComplexMessage = ({ content }: { content: MessageContent }) => {
  // If the content is a string, render it as markdown
  if (typeof content === 'string') {
    return renderMarkdown(content);
  }
  
  // If content is an object with text and table
  return (
    <div>
      {renderMarkdown(content.text)}
      <ProductTable tableData={content.table} />
    </div>
  );
};

const roles: GetProp<typeof Bubble.List, "roles"> = {
  ai: {
    placement: "start",
    avatar: { icon: <RobotOutlined />, style: { background: "#fde3cf" } },
    typing: { step: 5, interval: 20 },
    style: { maxWidth: 800 }, // Increased max width to accommodate tables
    messageRender: (content) => <ComplexMessage content={content} />, // Use complex message renderer
  },
  local: {
    placement: "end",
    avatar: { icon: <UserOutlined />, style: { background: "#87d068" } },
    messageRender: renderMarkdown,
  },
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
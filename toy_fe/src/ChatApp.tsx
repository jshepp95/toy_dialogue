import React from 'react';
import { UserOutlined, RobotOutlined } from '@ant-design/icons';
import { Bubble, Sender, useXAgent, useXChat } from '@ant-design/x';
import { Flex, type GetProp } from 'antd';

// Define roles for the chat bubbles
const roles: GetProp<typeof Bubble.List, 'roles'> = {
  ai: {
    placement: 'start',
    avatar: { icon: <RobotOutlined />, style: { background: '#fde3cf' } },
    typing: { step: 5, interval: 20 },
    style: {
      maxWidth: 600,
    },
  },
  local: {
    placement: 'end',
    avatar: { icon: <UserOutlined />, style: { background: '#87d068' } },
  },
};

const ChatApp = () => {
  const [content, setContent] = React.useState('');
  const webSocketRef = React.useRef<WebSocket | null>(null);
  const [threadId, setThreadId] = React.useState<string | null>(null);
  const [connecting, setConnecting] = React.useState(true);

  // Initialize WebSocket connection
  React.useEffect(() => {
    // Connect to WebSocket server
    const ws = new WebSocket('ws://localhost:8000/ws');
    webSocketRef.current = ws;

    // Handle connection opening
    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnecting(false);
    };

    // Handle connection closing
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnecting(true);
    };

    // Clean up on unmount
    return () => {
      ws.close();
    };
  }, []);

  // Configure the agent
  const [agent] = useXAgent({
    request: async ({ message }, { onSuccess, onError }) => {
      if (!webSocketRef.current || webSocketRef.current.readyState !== WebSocket.OPEN) {
        onError(new Error('WebSocket is not connected'));
        return;
      }

      try {
        // Send message to server - fixed TypeScript error
        if (message !== undefined) {
          webSocketRef.current.send(message);
        } else {
          onError(new Error("Message is undefined"));
          return;
        }

        // Handle responses from server
        const messageHandler = (event: MessageEvent) => {
          const data = event.data;
          // Check if it's a thread ID message
          if (typeof data === 'string' && data.startsWith('THREAD_ID:')) {
            const newThreadId = data.substring(10);
            setThreadId(newThreadId);
            return; // Skip this message as it's not a chat response
          }

          // Process as a normal message
          onSuccess(data);
          
          // Remove the event listener after success
          webSocketRef.current?.removeEventListener('message', messageHandler);
        };

        // Add event listener for this specific request
        webSocketRef.current.addEventListener('message', messageHandler);
      } catch (error) {
        onError(error instanceof Error ? error : new Error('Unknown error'));
      }
    },
  });

  // Use chat hook
  const { onRequest, messages } = useXChat({
    agent,
    requestPlaceholder: 'Waiting for response...',
    requestFallback: 'Failed to get a response. Please try again later.',
  });

  return (
    <Flex vertical gap="middle" style={{ maxWidth: 800, margin: '0 auto', padding: 20 }}>
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        {connecting ? (
          <div>Connecting to server...</div>
        ) : (
          <div>Connected! {threadId ? `Thread ID: ${threadId}` : ''}</div>
        )}
      </div>
      
      <Bubble.List
        roles={roles}
        style={{ height: 400, overflow: 'auto' }}
        items={messages.map(({ id, message, status }) => ({
          key: id,
          loading: status === 'loading',
          role: status === 'local' ? 'local' : 'ai',
          content: message,
        }))}
      />
      
      <Sender
        disabled={connecting}
        loading={agent.isRequesting()}
        value={content}
        onChange={setContent}
        onSubmit={(nextContent) => {
          onRequest(nextContent);
          setContent('');
        }}
        placeholder="Type your message here..."
      />
    </Flex>
  );
};

export default ChatApp;
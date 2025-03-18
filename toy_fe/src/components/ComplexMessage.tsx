import React from "react";
import { Typography } from "antd";
import markdownit from "markdown-it";
import InteractiveProductTable from "./InteractiveProductTable";

// Initialize markdown-it
const md = markdownit({ html: true, breaks: true });

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

// Define types for message content
type MessageContent = 
  | string 
  | {
      text: string;
      table: ProductTableData;
    }
  | {
      message: string;
      type?: string;
      [key: string]: any;  // Allow for other properties
    };

interface SelectedCategory {
  buyer_category: string;
  product_category: string;
  key: string | number;
}

// Define custom message component to handle complex messages
const ComplexMessage = ({ 
  content, 
  onSelectionApplied 
}: { 
  content: MessageContent, 
  onSelectionApplied?: (selected: SelectedCategory[]) => void
}) => {
  // Function to render markdown content
  const renderMarkdown = (text: string) => {
    if (typeof text !== 'string') {
      console.error("Expected string for markdown rendering, got:", text);
      return <Typography>Invalid content format</Typography>;
    }
    
    return (
      <Typography>
        <div dangerouslySetInnerHTML={{ __html: md.render(text) }} />
      </Typography>
    );
  };

  // If content is an object with text and table
  if (content && typeof content === 'object' && 'text' in content && 'table' in content) {
    return (
      <div>
        {renderMarkdown(content.text)}
        {content.table && (
          <InteractiveProductTable 
            tableData={content.table} 
            onSelectionApplied={onSelectionApplied}
          />
        )}
      </div>
    );
  }
  
  // If the content is a simple message (string)
  if (typeof content === 'string') {
    return renderMarkdown(content);
  }
  
  // Handle other types of responses (like audience_selection responses)
  if (content && typeof content === 'object') {
    // For response messages from selections
    if ('message' in content && typeof content.message === 'string') {
      return renderMarkdown(content.message);
    }
    
    // For other object types, render as JSON
    return (
      <Typography>
        <pre>{JSON.stringify(content, null, 2)}</pre>
      </Typography>
    );
  }
  
  // Fallback for other content types
  return <Typography>Unsupported content format</Typography>;
};

export default ComplexMessage;
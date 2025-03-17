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
type MessageContent = string | {
  text: string;
  table: ProductTableData;
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
  const renderMarkdown = (text: string) => (
    <Typography>
      <div dangerouslySetInnerHTML={{ __html: md.render(text) }} />
    </Typography>
  );

  // If the content is a string, render it as markdown
  if (typeof content === 'string') {
    return renderMarkdown(content);
  }
  
  // If content is an object with text and table
  return (
    <div>
      {renderMarkdown(content.text)}
      <InteractiveProductTable 
        tableData={content.table} 
        onSelectionApplied={onSelectionApplied}
      />
    </div>
  );
};

export default ComplexMessage;
import React, { useState } from "react";
import { Table, Button, Typography, Space, Tag } from "antd";

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
  key?: string | number;
}

interface ProductTableData {
  query: string;
  total_results: number;
  rows: TableRow[];
}

interface SelectedCategory {
  buyer_category: string;
  product_category: string;
  key: string | number;
}

// Define the component to render product tables with selection
const InteractiveProductTable = ({ 
  tableData,
  onSelectionApplied
}: { 
  tableData: ProductTableData, 
  onSelectionApplied?: (selected: SelectedCategory[]) => void 
}) => {
  const [selectedRows, setSelectedRows] = useState<SelectedCategory[]>([]);

  // Function to handle row selection
  const handleRowSelect = (record: TableRow) => {
    const key = record.key as string | number;
    const isSelected = selectedRows.some(row => row.key === key);
    
    if (isSelected) {
      setSelectedRows(selectedRows.filter(row => row.key !== key));
    } else {
      setSelectedRows([
        ...selectedRows, 
        {
          buyer_category: record.buyer_category,
          product_category: record.product_category,
          key
        }
      ]);
    }
  };
  
  // Create a unique tag identifier for each category combination
  const getCategoryTag = (record: TableRow) => {
    return `${record.buyer_category} > ${record.product_category}`;
  };

  // Prepare columns for Ant Design Table with the Action column
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
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: TableRow) => {
        const isSelected = selectedRows.some(row => row.key === record.key);
        return (
          <Button 
            type={isSelected ? "primary" : "default"}
            size="small"
            onClick={() => handleRowSelect(record)}
          >
            {isSelected ? 'Selected' : 'Select'}
          </Button>
        );
      },
    },
  ];

  return (
    <div>
      <Table 
        dataSource={tableData.rows.map((row, index) => ({ 
          ...row, 
          key: row.key || `${row.buyer_category}-${row.product_category}-${index}` 
        }))} 
        columns={columns} 
        pagination={false}
        size="small"
        style={{ marginTop: '10px', marginBottom: '10px' }}
        rowClassName={(record) => {
          const isSelected = selectedRows.some(row => row.key === record.key);
          return isSelected ? 'ant-table-row-selected' : '';
        }}
      />
      
      <div style={{ marginTop: '16px', borderTop: '1px solid #f0f0f0', paddingTop: '16px' }}>
        {selectedRows.length > 0 ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Typography.Text>
              Selected categories for audience building:
            </Typography.Text>
            <Space size={[0, 8]} wrap>
              {selectedRows.map(row => (
                <Tag
                  key={row.key}
                  closable
                  color="blue"
                  onClose={() => setSelectedRows(prev => prev.filter(r => r.key !== row.key))}
                >
                  {row.buyer_category} &gt; {row.product_category}
                </Tag>
              ))}
            </Space>
            <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'flex-end' }}>
              <Button 
                type="primary"
                onClick={() => {
                  if (onSelectionApplied) {
                    onSelectionApplied(selectedRows);
                  }
                }}
              >
                Apply Selection ({selectedRows.length})
              </Button>
            </div>
          </Space>
        ) : (
          <Typography.Text type="secondary">
            Select categories above to build your audience
          </Typography.Text>
        )}
      </div>
    </div>
  );
};

export default InteractiveProductTable;
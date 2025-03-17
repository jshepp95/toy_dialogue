import sqlite3
import json

from langchain.tools import BaseTool
from typing import Type, ClassVar
from pydantic import BaseModel, Field
from schema import ProductDetails, ProductSearchResults

from collections import defaultdict

DB_PATH = "/home/azureuser/projects/whizzbang_audience/db/db.db"

class SKULookupInput(BaseModel):
    sku: str = Field(..., description="The product SKU to lookup")

class ProductLookupInput(BaseModel):
    sku: str = Field(..., description="The product name to lookup")

class SKULookupTool(BaseTool):
    name: ClassVar[str] = "product_database_lookup"
    description: ClassVar[str] = "Use this tool to look up a product in the database by its SKU"
    args_schema: ClassVar[Type[BaseModel]] = SKULookupInput

    def _run(self, sku: str) -> ProductDetails:
        """ Query the database for product details """
        db_path = DB_PATH

        try:
            print(f"Querying database for SKU: {sku}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            query = """
            SELECT skuId, skuName, catLevel4Name, catLevel5Name
            FROM DIM_ITEMS
            WHERE skuId = ?
            """
            cursor.execute(query, (sku,))
            result = cursor.fetchone()
            conn.close()

            print(result)

            if result:
                return ProductDetails(
                    sku=result[0],
                    product_name=result[1],
                    buyer_category=result[2],
                    product_category=result[3]
                )
            else:
                raise ValueError(f"Product with SKU {sku} not found")
            
        except sqlite3.Error as e:
            raise ValueError(f"DB Error: {e}")
        

class ProductLookupTool(BaseTool):
    name: ClassVar[str] = "product_database_lookup"
    description: ClassVar[str] = "Use this tool to look up a product in the database by its name"
    args_schema: ClassVar[Type[BaseModel]] = ProductLookupInput

    def _run(self, name: str) -> ProductSearchResults:
        """ Query the database for product details and group by categories """
        db_path = DB_PATH

        try:
            print(f"Querying database for name: {name}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            query = """
            SELECT 
                skuId,
                skuName,
                catLevel4Name,
                catLevel5Name
            FROM 
                DIM_ITEMS
            WHERE 
                (
                    skuName LIKE ? || '%' OR
                    skuName LIKE '%' || ? OR
                    skuName LIKE '%' || ? || '%'
                )
                AND catLevel4Name != 'NOT IN USE'
                AND catLevel5Name != 'NOT IN USE'
            ORDER BY 
                CASE
                    WHEN skuName = ? THEN 10
                    WHEN skuName LIKE ? || '%' THEN 8
                    WHEN skuName LIKE '%' || ? || '%' THEN 6
                    ELSE 1
                END DESC
            LIMIT 10;
            """
            
            params = (name, name, name, name, name, name)
            cursor.execute(query, params)
            
            results = cursor.fetchall()
            conn.close()

            print(f"Found {len(results)} results")
            
            if results:
                # Build a dictionary to group products by categories
                by_buyer_category = defaultdict(list)
                by_product_category = defaultdict(list)
                
                # Also track unique categories
                unique_buyer_categories = set()
                unique_product_categories = set()
                
                # Process all results
                all_products = []
                for row in results:
                    sku_id = row[0]
                    product_name = row[1]
                    buyer_category = row[2]
                    product_category = row[3]

                    if buyer_category == 'NOT IN USE' or product_category == 'NOT IN USE':
                        print(f"Filtering out product {product_name} with category 'NOT IN USE'")
                        continue
                    
                    # Create product object
                    product = ProductDetails(
                        sku=sku_id,
                        product_name=product_name,
                        buyer_category=buyer_category,
                        product_category=product_category
                    )
                    
                    # Add to our collections
                    all_products.append(product)
                    by_buyer_category[buyer_category].append(product)
                    by_product_category[product_category].append(product)
                    
                    # Track unique categories
                    unique_buyer_categories.add(buyer_category)
                    unique_product_categories.add(product_category)
                
                # Build the response object
                response = ProductSearchResults(
                    query=name,
                    total_results=len(results),
                    unique_buyer_categories=list(unique_buyer_categories),
                    unique_product_categories=list(unique_product_categories),
                    by_buyer_category=dict(by_buyer_category),
                    by_product_category=dict(by_product_category),
                    all_products=all_products
                )
                
                print(f"\nFound products in {len(unique_buyer_categories)} buyer categories and {len(unique_product_categories)} product categories\n")
                
                with open("res.json", "w") as f:
                    # Convert to dict first
                    result_dict = response.model_dump()
                    json.dump(result_dict, f)
                
                return response
            else:
                raise ValueError(f"Product with name {name} not found")
            
        except sqlite3.Error as e:
            raise ValueError(f"DB Error: {e}")
        

def transform_to_product_table(product_search_results: ProductSearchResults):
    """
    Transform ProductSearchResults into a structured table format with:
    - Buyer Category
    - Product Category
    - Sample SKUs
    - Total SKU Count
    
    Returns a dictionary with the table data and metadata
    """
    # Create a structure to track unique buyer/product category combinations
    category_combinations = {}
    
    # Group products by buyer category and product category
    for product in product_search_results.all_products:
        buyer_cat = product.buyer_category
        product_cat = product.product_category
        
        # Create a unique key for this combination
        combo_key = f"{buyer_cat}|||{product_cat}"
        
        if combo_key not in category_combinations:
            category_combinations[combo_key] = {
                "buyer_category": buyer_cat,
                "product_category": product_cat,
                "skus": [],
                "count": 0
            }
        
        # Add this product's SKU to the list (if not already at 5)
        if len(category_combinations[combo_key]["skus"]) < 2:
            category_combinations[combo_key]["skus"].append({
                "sku": product.sku,
                "name": product.product_name
            })
        
        # Increment the count
        category_combinations[combo_key]["count"] += 1
    
    # Convert to a list of rows for easier frontend rendering
    table_rows = list(category_combinations.values())
    
    # Create the final structure
    table_data = {
        "query": product_search_results.query,
        "total_results": product_search_results.total_results,
        "rows": table_rows
    }
    
    return table_data
        

            





# schema.py
from typing import Annotated, List, Optional, Union, TypedDict, Dict
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage

class ProductIdentification(BaseModel):
    """Schema for initial product identification from user message"""
    # sku: Optional[str] = Field(None, description="The product SKU")
    mentioned: bool = Field(..., description="Whether a product was mentioned in the message")
    product_name: Optional[str] = Field(None, description="The product name")

class ProductDetails(BaseModel):
    """Schema for product details after database lookup"""
    sku: Union[str, int] = Field(..., description="The product SKU")
    product_name: str = Field(None, description="The identified product name")
    buyer_category: Optional[str] = Field(None, description="The buyer category (L4)")
    product_category: Optional[str] = Field(None, description="The product category (L5)")

class ProductSearchResults(BaseModel):
    query: str
    total_results: int
    unique_buyer_categories: List[str]
    unique_product_categories: List[str]
    by_buyer_category: Dict[str, List[ProductDetails]]
    by_product_category: Dict[str, List[ProductDetails]]
    all_products: List[ProductDetails]

class SelectedCategory(BaseModel):
    """Schema for selected audience category"""
    buyer_category: str = Field(..., description="The buyer category")
    product_category: str = Field(..., description="The product category")

class AudienceSelections(BaseModel):
    """Schema for audience building selections"""
    categories: List[SelectedCategory] = Field(default_factory=list, description="Selected categories")
    created_at: Optional[str] = Field(None, description="When the audience was created")

class AudienceBuilderState(TypedDict):
    conversation_history: Annotated[List[Union[HumanMessage, AIMessage, Dict]], "conversation history", "append"]
    sku: Annotated[Optional[str], "The product sku the user wants"]
    product_name: Annotated[Optional[str], "Product name from DB"]
    product_category: Annotated[Optional[str], "Product category from DB"]
    buyer_category: Annotated[Optional[str], "Buyer category from DB"]
    product_search_results: Annotated[Optional[ProductSearchResults], "Product search results from DB"]
    product_table: Annotated[Optional[Dict], "Structured table data for UI rendering"]
    audience_selections: Annotated[Optional[AudienceSelections], "User's audience building selections"]
    current_node: str
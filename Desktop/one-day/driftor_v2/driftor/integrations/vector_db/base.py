"""
Base vector database interface for similarity search and document storage.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class VectorDBType(Enum):
    """Supported vector database types."""
    CHROMADB = "chromadb"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"


class SearchResult:
    """Vector search result."""
    
    def __init__(
        self,
        document_id: str,
        content: str,
        metadata: Dict[str, Any],
        score: float,
        distance: float = None
    ):
        self.document_id = document_id
        self.content = content
        self.metadata = metadata
        self.score = score
        self.distance = distance or (1.0 - score) if score is not None else None


class BaseVectorDB(ABC):
    """Abstract base class for vector database operations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the vector database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the vector database."""
        pass
    
    @abstractmethod
    async def create_collection(
        self, 
        collection_name: str, 
        dimension: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create a new collection/index."""
        pass
    
    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection/index."""
        pass
    
    @abstractmethod
    async def list_collections(self) -> List[str]:
        """List available collections."""
        pass
    
    @abstractmethod
    async def upsert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """Insert or update documents in the collection."""
        pass
    
    @abstractmethod
    async def delete_documents(
        self,
        collection_name: str,
        document_ids: List[str]
    ) -> bool:
        """Delete documents from the collection."""
        pass
    
    @abstractmethod
    async def similarity_search(
        self,
        collection_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """Perform similarity search."""
        pass
    
    @abstractmethod
    async def get_document(
        self,
        collection_name: str,
        document_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check database health and connection status."""
        pass
    
    def is_connected(self) -> bool:
        """Check if connected to the database."""
        return self._connected
    
    async def ensure_connected(self) -> bool:
        """Ensure database connection is active."""
        if not self.is_connected():
            return await self.connect()
        return True


class DocumentProcessor:
    """Helper class for processing documents before vector storage."""
    
    @staticmethod
    def prepare_ticket_document(
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Prepare a ticket for vector storage."""
        summary = ticket_data.get("summary", "")
        description = ticket_data.get("description", "") or ""
        
        # Combine text content
        content = f"{summary}\n\n{description}".strip()
        
        # Prepare metadata
        metadata = {
            "ticket_key": ticket_data.get("key", ""),
            "tenant_id": tenant_id,
            "summary": summary,
            "description": description[:500],  # Truncate for metadata
            "issue_type": ticket_data.get("issue_type", ""),
            "priority": ticket_data.get("priority", ""),
            "status": ticket_data.get("status", ""),
            "component": classification.get("component", "unknown"),
            "severity": classification.get("severity", "unknown"),
            "is_bug": classification.get("is_bug", False),
            "keywords": classification.get("keywords", [])[:10],  # Limit keywords
            "created_at": ticket_data.get("created", ""),
            "assignee": ticket_data.get("assignee", {}).get("displayName", ""),
            "reporter": ticket_data.get("reporter", {}).get("displayName", ""),
            "labels": ticket_data.get("labels", [])[:5],  # Limit labels
            "document_type": "ticket"
        }
        
        return {
            "id": f"ticket_{tenant_id}_{ticket_data.get('key', '')}",
            "content": content,
            "metadata": metadata
        }
    
    @staticmethod
    def prepare_documentation_document(
        doc_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Prepare documentation for vector storage."""
        title = doc_data.get("title", "")
        content = doc_data.get("content", "") or doc_data.get("excerpt", "")
        
        # Combine title and content
        full_content = f"{title}\n\n{content}".strip()
        
        # Prepare metadata
        metadata = {
            "tenant_id": tenant_id,
            "title": title,
            "url": doc_data.get("url", ""),
            "source": doc_data.get("source", ""),
            "doc_type": doc_data.get("doc_type", "general"),
            "space": doc_data.get("space", ""),
            "author": doc_data.get("author", ""),
            "last_modified": doc_data.get("last_modified", ""),
            "document_type": "documentation"
        }
        
        return {
            "id": f"doc_{tenant_id}_{hash(doc_data.get('url', title))}",
            "content": full_content,
            "metadata": metadata
        }
    
    @staticmethod
    def prepare_code_document(
        file_data: Dict[str, Any],
        repo_info: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Prepare code file for vector storage."""
        path = file_data.get("path", "")
        content = file_data.get("content", "")
        
        # Prepare metadata
        metadata = {
            "tenant_id": tenant_id,
            "file_path": path,
            "file_name": file_data.get("name", ""),
            "repository": f"{repo_info.get('owner', '')}/{repo_info.get('repo', '')}",
            "branch": repo_info.get("branch", "main"),
            "language": file_data.get("language", ""),
            "size": len(content),
            "url": file_data.get("url", ""),
            "document_type": "code"
        }
        
        return {
            "id": f"code_{tenant_id}_{hash(f"{repo_info.get('repo', '')}_{path}")}",
            "content": content,
            "metadata": metadata
        }


class VectorDBError(Exception):
    """Base exception for vector database operations."""
    pass


class ConnectionError(VectorDBError):
    """Vector database connection error."""
    pass


class CollectionError(VectorDBError):
    """Collection/index operation error."""
    pass


class SearchError(VectorDBError):
    """Search operation error."""
    pass
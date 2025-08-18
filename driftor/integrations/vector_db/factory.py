"""
Vector database factory and management.
"""
from typing import Dict, Optional, Any
import structlog

from .base import BaseVectorDB, VectorDBType
from .chromadb_client import ChromaDBClient
from driftor.core.config import get_settings

logger = structlog.get_logger(__name__)


class VectorDBFactory:
    """Factory for creating vector database instances."""
    
    @staticmethod
    def create_client(
        db_type: VectorDBType,
        config: Dict[str, Any]
    ) -> BaseVectorDB:
        """Create a vector database client instance."""
        
        if db_type == VectorDBType.CHROMADB:
            return ChromaDBClient(config)
        elif db_type == VectorDBType.PINECONE:
            # TODO: Implement Pinecone client
            raise NotImplementedError("Pinecone client not yet implemented")
        elif db_type == VectorDBType.WEAVIATE:
            # TODO: Implement Weaviate client
            raise NotImplementedError("Weaviate client not yet implemented")
        elif db_type == VectorDBType.QDRANT:
            # TODO: Implement Qdrant client
            raise NotImplementedError("Qdrant client not yet implemented")
        else:
            raise ValueError(f"Unsupported vector database type: {db_type}")


class VectorDBManager:
    """Manager for vector database operations and client lifecycle."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[BaseVectorDB] = None
        self._client_config = None
    
    async def get_client(self, force_reconnect: bool = False) -> Optional[BaseVectorDB]:
        """Get or create vector database client."""
        try:
            # Check if we need to create/reconnect client
            current_config = self._get_current_config()
            
            if (self._client is None or 
                force_reconnect or 
                self._client_config != current_config):
                
                # Disconnect existing client
                if self._client:
                    await self._client.disconnect()
                
                # Create new client
                db_type = VectorDBType(current_config.get("type", "chromadb"))
                self._client = VectorDBFactory.create_client(db_type, current_config)
                self._client_config = current_config
                
                # Connect to database
                connected = await self._client.connect()
                if not connected:
                    logger.error("Failed to connect to vector database")
                    self._client = None
                    return None
                
                logger.info(
                    "Vector database client created",
                    db_type=db_type.value,
                    connected=connected
                )
            
            return self._client
            
        except Exception as e:
            logger.error("Failed to get vector database client", error=str(e))
            return None
    
    def _get_current_config(self) -> Dict[str, Any]:
        """Get current vector database configuration."""
        return {
            "type": self.settings.vector_db.type,
            "host": self.settings.vector_db.host,
            "port": self.settings.vector_db.port,
            "ssl": self.settings.vector_db.ssl,
            "headers": getattr(self.settings.vector_db, 'headers', {}),
            "embedding_model": getattr(self.settings.vector_db, 'embedding_model', 'all-MiniLM-L6-v2')
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check vector database health."""
        try:
            client = await self.get_client()
            if not client:
                return {
                    "healthy": False,
                    "status": "no_client",
                    "error": "No vector database client available"
                }
            
            return await client.health_check()
            
        except Exception as e:
            logger.error("Vector database health check failed", error=str(e))
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    async def ensure_tenant_setup(self, tenant_id: str) -> bool:
        """Ensure vector database is properly set up for a tenant."""
        try:
            client = await self.get_client()
            if not client:
                return False
            
            # For ChromaDB, ensure collections exist
            if hasattr(client, 'ensure_tenant_collections'):
                return await client.ensure_tenant_collections(tenant_id)
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to ensure tenant vector DB setup",
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
    
    async def cleanup_tenant(self, tenant_id: str) -> bool:
        """Clean up tenant data from vector database."""
        try:
            client = await self.get_client()
            if not client:
                return False
            
            # For ChromaDB, clean up collections
            if hasattr(client, 'cleanup_tenant_data'):
                return await client.cleanup_tenant_data(tenant_id)
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to cleanup tenant vector DB data",
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from vector database."""
        if self._client:
            try:
                await self._client.disconnect()
                logger.info("Vector database client disconnected")
            except Exception as e:
                logger.warning("Error during vector database disconnect", error=str(e))
            finally:
                self._client = None
                self._client_config = None


# Global instance
_vector_db_manager: Optional[VectorDBManager] = None


def get_vector_db_manager() -> VectorDBManager:
    """Get global vector database manager."""
    global _vector_db_manager
    
    if _vector_db_manager is None:
        _vector_db_manager = VectorDBManager()
    
    return _vector_db_manager


async def get_vector_db_client() -> Optional[BaseVectorDB]:
    """Get vector database client."""
    manager = get_vector_db_manager()
    return await manager.get_client()


class VectorDBService:
    """High-level service for vector database operations."""
    
    def __init__(self):
        self.manager = get_vector_db_manager()
    
    async def index_ticket(
        self,
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any],
        tenant_id: str
    ) -> bool:
        """Index a ticket in the vector database."""
        try:
            client = await self.manager.get_client()
            if not client:
                return False
            
            # Ensure tenant setup
            await self.manager.ensure_tenant_setup(tenant_id)
            
            # Prepare document
            from .base import DocumentProcessor
            doc = DocumentProcessor.prepare_ticket_document(
                ticket_data, classification, tenant_id
            )
            
            # Upsert document
            collection_name = f"tickets_{tenant_id}"
            success = await client.upsert_documents(collection_name, [doc])
            
            if success:
                logger.info(
                    "Ticket indexed in vector database",
                    ticket_key=ticket_data.get("key"),
                    tenant_id=tenant_id
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to index ticket",
                ticket_key=ticket_data.get("key", "unknown"),
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
    
    async def index_documentation(
        self,
        docs: List[Dict[str, Any]],
        tenant_id: str
    ) -> bool:
        """Index documentation in the vector database."""
        try:
            client = await self.manager.get_client()
            if not client:
                return False
            
            # Ensure tenant setup
            await self.manager.ensure_tenant_setup(tenant_id)
            
            # Prepare documents
            from .base import DocumentProcessor
            prepared_docs = []
            for doc in docs:
                prepared_doc = DocumentProcessor.prepare_documentation_document(doc, tenant_id)
                prepared_docs.append(prepared_doc)
            
            # Upsert documents
            collection_name = f"documentation_{tenant_id}"
            success = await client.upsert_documents(collection_name, prepared_docs)
            
            if success:
                logger.info(
                    "Documentation indexed in vector database",
                    doc_count=len(docs),
                    tenant_id=tenant_id
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to index documentation",
                doc_count=len(docs),
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
    
    async def index_code_files(
        self,
        files: List[Dict[str, Any]],
        repo_info: Dict[str, Any],
        tenant_id: str
    ) -> bool:
        """Index code files in the vector database."""
        try:
            client = await self.manager.get_client()
            if not client:
                return False
            
            # Ensure tenant setup
            await self.manager.ensure_tenant_setup(tenant_id)
            
            # Prepare documents
            from .base import DocumentProcessor
            prepared_docs = []
            for file_data in files:
                prepared_doc = DocumentProcessor.prepare_code_document(
                    file_data, repo_info, tenant_id
                )
                prepared_docs.append(prepared_doc)
            
            # Upsert documents
            collection_name = f"code_{tenant_id}"
            success = await client.upsert_documents(collection_name, prepared_docs)
            
            if success:
                logger.info(
                    "Code files indexed in vector database",
                    file_count=len(files),
                    tenant_id=tenant_id
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to index code files",
                file_count=len(files),
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
    
    async def search_similar_tickets(
        self,
        query_text: str,
        tenant_id: str,
        n_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar tickets."""
        try:
            client = await self.manager.get_client()
            if not client:
                return []
            
            collection_name = f"tickets_{tenant_id}"
            
            # Prepare filters
            where_clause = {"tenant_id": tenant_id}
            if filters:
                where_clause.update(filters)
            
            # Perform search
            results = await client.similarity_search(
                collection_name=collection_name,
                query_text=query_text,
                n_results=n_results,
                where=where_clause
            )
            
            # Convert to dict format
            similar_tickets = []
            for result in results:
                similar_tickets.append({
                    "document_id": result.document_id,
                    "content": result.content,
                    "metadata": result.metadata,
                    "score": result.score,
                    "distance": result.distance
                })
            
            return similar_tickets
            
        except Exception as e:
            logger.error(
                "Similar ticket search failed",
                tenant_id=tenant_id,
                error=str(e)
            )
            return []
    
    async def search_documentation(
        self,
        query_text: str,
        tenant_id: str,
        n_results: int = 10,
        doc_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documentation."""
        try:
            client = await self.manager.get_client()
            if not client:
                return []
            
            collection_name = f"documentation_{tenant_id}"
            
            # Prepare filters
            where_clause = {"tenant_id": tenant_id}
            if doc_types:
                where_clause["doc_type"] = {"$in": doc_types}
            
            # Perform search
            results = await client.similarity_search(
                collection_name=collection_name,
                query_text=query_text,
                n_results=n_results,
                where=where_clause
            )
            
            # Convert to dict format
            documentation = []
            for result in results:
                documentation.append({
                    "document_id": result.document_id,
                    "content": result.content,
                    "metadata": result.metadata,
                    "score": result.score,
                    "distance": result.distance
                })
            
            return documentation
            
        except Exception as e:
            logger.error(
                "Documentation search failed",
                tenant_id=tenant_id,
                error=str(e)
            )
            return []
    
    async def search_code(
        self,
        query_text: str,
        tenant_id: str,
        n_results: int = 10,
        language: Optional[str] = None,
        repository: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant code files."""
        try:
            client = await self.manager.get_client()
            if not client:
                return []
            
            collection_name = f"code_{tenant_id}"
            
            # Prepare filters
            where_clause = {"tenant_id": tenant_id}
            if language:
                where_clause["language"] = language
            if repository:
                where_clause["repository"] = repository
            
            # Perform search
            results = await client.similarity_search(
                collection_name=collection_name,
                query_text=query_text,
                n_results=n_results,
                where=where_clause
            )
            
            # Convert to dict format
            code_files = []
            for result in results:
                code_files.append({
                    "document_id": result.document_id,
                    "content": result.content,
                    "metadata": result.metadata,
                    "score": result.score,
                    "distance": result.distance
                })
            
            return code_files
            
        except Exception as e:
            logger.error(
                "Code search failed",
                tenant_id=tenant_id,
                error=str(e)
            )
            return []


# Global service instance
def get_vector_db_service() -> VectorDBService:
    """Get vector database service."""
    return VectorDBService()
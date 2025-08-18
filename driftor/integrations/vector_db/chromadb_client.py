"""
ChromaDB vector database client implementation.
"""
import asyncio
from typing import Dict, List, Optional, Any, Union
import structlog
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from .base import BaseVectorDB, SearchResult, VectorDBError, ConnectionError, CollectionError, SearchError
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class ChromaDBClient(BaseVectorDB):
    """ChromaDB implementation of vector database."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # ChromaDB configuration
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8000)
        self.ssl = config.get("ssl", False)
        self.headers = config.get("headers", {})
        
        # Embedding configuration
        self.embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.embedding_function = None
        
        # Client settings
        self.settings = Settings(
            chroma_server_host=self.host,
            chroma_server_http_port=self.port,
            chroma_server_ssl_enabled=self.ssl,
            chroma_server_headers=self.headers,
            anonymized_telemetry=False
        )
    
    async def connect(self) -> bool:
        """Connect to ChromaDB server."""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.HttpClient(settings=self.settings)
            
            # Initialize embedding function
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            
            # Test connection
            heartbeat = self.client.heartbeat()
            
            self._connected = True
            
            logger.info(
                "ChromaDB connection established",
                host=self.host,
                port=self.port,
                heartbeat=heartbeat
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "ChromaDB connection failed",
                host=self.host,
                port=self.port,
                error=str(e)
            )
            self._connected = False
            raise ConnectionError(f"Failed to connect to ChromaDB: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from ChromaDB."""
        try:
            if self.client:
                # ChromaDB client doesn't have explicit disconnect
                self.client = None
                self.embedding_function = None
                self._connected = False
                
                logger.info("ChromaDB disconnected")
                
        except Exception as e:
            logger.warning("Error during ChromaDB disconnect", error=str(e))
    
    async def create_collection(
        self, 
        collection_name: str, 
        dimension: int = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create a new ChromaDB collection."""
        try:
            await self.ensure_connected()
            
            # ChromaDB handles dimensions automatically
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                metadata=metadata or {}
            )
            
            logger.info(
                "ChromaDB collection created",
                collection_name=collection_name,
                metadata=metadata
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "ChromaDB collection creation failed",
                collection_name=collection_name,
                error=str(e)
            )
            raise CollectionError(f"Failed to create collection {collection_name}: {str(e)}")
    
    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a ChromaDB collection."""
        try:
            await self.ensure_connected()
            
            self.client.delete_collection(name=collection_name)
            
            logger.info(
                "ChromaDB collection deleted",
                collection_name=collection_name
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "ChromaDB collection deletion failed",
                collection_name=collection_name,
                error=str(e)
            )
            raise CollectionError(f"Failed to delete collection {collection_name}: {str(e)}")
    
    async def list_collections(self) -> List[str]:
        """List available ChromaDB collections."""
        try:
            await self.ensure_connected()
            
            collections = self.client.list_collections()
            collection_names = [col.name for col in collections]
            
            logger.debug(
                "ChromaDB collections listed",
                count=len(collection_names),
                collections=collection_names
            )
            
            return collection_names
            
        except Exception as e:
            logger.error("ChromaDB collection listing failed", error=str(e))
            raise CollectionError(f"Failed to list collections: {str(e)}")
    
    async def upsert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """Insert or update documents in ChromaDB collection."""
        try:
            await self.ensure_connected()
            
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            # Prepare data for ChromaDB
            ids = []
            texts = []
            metadatas = []
            
            for doc in documents:
                ids.append(doc["id"])
                texts.append(doc["content"])
                metadatas.append(doc["metadata"])
            
            # Upsert documents
            collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            
            logger.info(
                "ChromaDB documents upserted",
                collection_name=collection_name,
                document_count=len(documents)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "ChromaDB document upsert failed",
                collection_name=collection_name,
                document_count=len(documents),
                error=str(e)
            )
            raise VectorDBError(f"Failed to upsert documents: {str(e)}")
    
    async def delete_documents(
        self,
        collection_name: str,
        document_ids: List[str]
    ) -> bool:
        """Delete documents from ChromaDB collection."""
        try:
            await self.ensure_connected()
            
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            collection.delete(ids=document_ids)
            
            logger.info(
                "ChromaDB documents deleted",
                collection_name=collection_name,
                document_count=len(document_ids)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "ChromaDB document deletion failed",
                collection_name=collection_name,
                document_count=len(document_ids),
                error=str(e)
            )
            raise VectorDBError(f"Failed to delete documents: {str(e)}")
    
    async def similarity_search(
        self,
        collection_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """Perform similarity search in ChromaDB."""
        try:
            await self.ensure_connected()
            
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            # Prepare query
            query_params = {
                "n_results": n_results,
                "include": include or ["documents", "metadatas", "distances"]
            }
            
            if where:
                query_params["where"] = where
            
            if query_text:
                query_params["query_texts"] = [query_text]
            elif query_vector:
                query_params["query_embeddings"] = [query_vector]
            else:
                raise SearchError("Either query_text or query_vector must be provided")
            
            # Execute search
            results = collection.query(**query_params)
            
            # Convert to SearchResult objects
            search_results = []
            
            if results.get("ids"):
                for i, doc_id in enumerate(results["ids"][0]):
                    content = results.get("documents", [[]])[0][i] if results.get("documents") else ""
                    metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                    distance = results.get("distances", [[]])[0][i] if results.get("distances") else 0.0
                    score = 1.0 - distance if distance is not None else 1.0
                    
                    search_results.append(SearchResult(
                        document_id=doc_id,
                        content=content,
                        metadata=metadata or {},
                        score=max(0.0, score),
                        distance=distance
                    ))
            
            logger.info(
                "ChromaDB similarity search completed",
                collection_name=collection_name,
                query_length=len(query_text) if query_text else 0,
                results_count=len(search_results),
                n_results=n_results
            )
            
            return search_results
            
        except Exception as e:
            logger.error(
                "ChromaDB similarity search failed",
                collection_name=collection_name,
                error=str(e)
            )
            raise SearchError(f"Similarity search failed: {str(e)}")
    
    async def get_document(
        self,
        collection_name: str,
        document_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID from ChromaDB."""
        try:
            await self.ensure_connected()
            
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            results = collection.get(
                ids=[document_id],
                include=["documents", "metadatas"]
            )
            
            if results.get("ids") and results["ids"]:
                return {
                    "id": results["ids"][0],
                    "content": results.get("documents", [""])[0],
                    "metadata": results.get("metadatas", [{}])[0] or {}
                }
            
            return None
            
        except Exception as e:
            logger.error(
                "ChromaDB document retrieval failed",
                collection_name=collection_name,
                document_id=document_id,
                error=str(e)
            )
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ChromaDB health and connection status."""
        try:
            if not self.is_connected():
                return {
                    "healthy": False,
                    "status": "disconnected",
                    "error": "Not connected to ChromaDB"
                }
            
            # Test basic operations
            heartbeat = self.client.heartbeat()
            collections = self.client.list_collections()
            
            return {
                "healthy": True,
                "status": "connected",
                "heartbeat": heartbeat,
                "collections_count": len(collections),
                "version": self.client.get_version(),
                "embedding_model": self.embedding_model
            }
            
        except Exception as e:
            logger.error("ChromaDB health check failed", error=str(e))
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a specific collection."""
        try:
            await self.ensure_connected()
            
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            # Get collection stats
            count_result = collection.count()
            
            return {
                "name": collection_name,
                "document_count": count_result,
                "metadata": collection.metadata or {}
            }
            
        except Exception as e:
            logger.error(
                "ChromaDB collection info retrieval failed",
                collection_name=collection_name,
                error=str(e)
            )
            return {
                "name": collection_name,
                "error": str(e)
            }
    
    async def ensure_tenant_collections(self, tenant_id: str) -> bool:
        """Ensure all required collections exist for a tenant."""
        try:
            collections_to_create = [
                f"tickets_{tenant_id}",
                f"documentation_{tenant_id}", 
                f"code_{tenant_id}"
            ]
            
            existing_collections = await self.list_collections()
            
            for collection_name in collections_to_create:
                if collection_name not in existing_collections:
                    await self.create_collection(
                        collection_name=collection_name,
                        metadata={
                            "tenant_id": tenant_id,
                            "created_at": str(asyncio.get_event_loop().time()),
                            "description": f"Vector storage for {collection_name.split('_')[0]}"
                        }
                    )
                    
                    logger.info(
                        "Tenant collection created",
                        tenant_id=tenant_id,
                        collection_name=collection_name
                    )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to ensure tenant collections",
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
    
    async def cleanup_tenant_data(self, tenant_id: str) -> bool:
        """Clean up all data for a tenant (GDPR compliance)."""
        try:
            collections_to_clean = [
                f"tickets_{tenant_id}",
                f"documentation_{tenant_id}",
                f"code_{tenant_id}"
            ]
            
            existing_collections = await self.list_collections()
            
            for collection_name in collections_to_clean:
                if collection_name in existing_collections:
                    await self.delete_collection(collection_name)
                    
                    logger.info(
                        "Tenant collection cleaned up",
                        tenant_id=tenant_id,
                        collection_name=collection_name
                    )
            
            # Audit the cleanup
            await audit(
                event_type=AuditEventType.DATA_DELETED,
                tenant_id=tenant_id,
                resource_type="vector_db_cleanup",
                resource_id=tenant_id,
                details={
                    "collections_deleted": collections_to_clean,
                    "reason": "tenant_data_cleanup"
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to cleanup tenant data",
                tenant_id=tenant_id,
                error=str(e)
            )
            return False
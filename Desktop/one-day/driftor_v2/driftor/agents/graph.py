"""
LangGraph workflow orchestration for ticket analysis and code fixing.
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import structlog

from driftor.security.audit import audit, AuditEventType, AuditSeverity

logger = structlog.get_logger(__name__)


class TicketAnalysisState(TypedDict):
    """State for the ticket analysis workflow."""
    # Input data
    tenant_id: str
    ticket_id: str
    ticket_data: Dict[str, any]
    assignee_id: str
    
    # Processing results
    ticket_classification: Optional[Dict[str, any]]
    similar_tickets: List[Dict[str, any]]
    relevant_docs: List[Dict[str, any]]
    repository_info: Optional[Dict[str, any]]
    code_analysis: Optional[Dict[str, any]]
    suggested_fix: Optional[str]
    confidence_score: float
    
    # Workflow control
    workflow_status: str  # "processing", "completed", "failed"
    current_step: str
    error_message: Optional[str]
    
    # Communication
    messages: Annotated[List[BaseMessage], add_messages]
    notification_sent: bool
    message_id: Optional[str]
    
    # Metadata
    started_at: datetime
    completed_at: Optional[datetime]
    processing_time_seconds: Optional[float]


class TicketAnalysisWorkflow:
    """Main workflow orchestrator for ticket analysis."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow."""
        # Initialize workflow
        workflow = StateGraph(TicketAnalysisState)
        
        # Add nodes (agents)
        workflow.add_node("classifier", self._classify_ticket_node)
        workflow.add_node("similarity_search", self._search_similar_tickets_node)
        workflow.add_node("doc_retrieval", self._retrieve_documentation_node)
        workflow.add_node("repo_mapper", self._map_repository_node)
        workflow.add_node("code_scanner", self._scan_code_node)
        workflow.add_node("fix_generator", self._generate_fix_node)
        workflow.add_node("confidence_scorer", self._calculate_confidence_node)
        workflow.add_node("notifier", self._send_notification_node)
        workflow.add_node("error_handler", self._handle_error_node)
        
        # Define workflow edges
        workflow.set_entry_point("classifier")
        
        # Parallel execution paths
        workflow.add_conditional_edges(
            "classifier",
            self._route_after_classification,
            {
                "continue": ["similarity_search", "doc_retrieval", "repo_mapper"],
                "skip": "confidence_scorer",
                "error": "error_handler"
            }
        )
        
        # Convergence after parallel execution
        workflow.add_edge(["similarity_search", "doc_retrieval", "repo_mapper"], "code_scanner")
        workflow.add_edge("code_scanner", "fix_generator")
        workflow.add_edge("fix_generator", "confidence_scorer")
        workflow.add_edge("confidence_scorer", "notifier")
        workflow.add_edge("notifier", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    async def run_analysis(self, initial_state: Dict[str, any]) -> TicketAnalysisState:
        """Run the complete ticket analysis workflow."""
        # Initialize state
        state = TicketAnalysisState(
            # Input data
            tenant_id=initial_state["tenant_id"],
            ticket_id=initial_state["ticket_id"],
            ticket_data=initial_state["ticket_data"],
            assignee_id=initial_state["assignee_id"],
            
            # Initialize processing results
            ticket_classification=None,
            similar_tickets=[],
            relevant_docs=[],
            repository_info=None,
            code_analysis=None,
            suggested_fix=None,
            confidence_score=0.0,
            
            # Initialize workflow control
            workflow_status="processing",
            current_step="classifier",
            error_message=None,
            
            # Initialize communication
            messages=[],
            notification_sent=False,
            message_id=None,
            
            # Initialize metadata
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            processing_time_seconds=None
        )
        
        try:
            # Audit workflow start
            await audit(
                event_type=AuditEventType.TICKET_ANALYZED,
                tenant_id=state["tenant_id"],
                resource_type="ticket",
                resource_id=state["ticket_id"],
                action="WORKFLOW_START",
                details={
                    "ticket_key": state["ticket_data"].get("key"),
                    "assignee": state["assignee_id"]
                }
            )
            
            # Execute workflow
            result = await self.workflow.ainvoke(state)
            
            # Calculate processing time
            if result.get("completed_at"):
                processing_time = (result["completed_at"] - result["started_at"]).total_seconds()
                result["processing_time_seconds"] = processing_time
            
            # Audit workflow completion
            await audit(
                event_type=AuditEventType.TICKET_ANALYZED,
                tenant_id=result["tenant_id"],
                resource_type="ticket",
                resource_id=result["ticket_id"],
                action="WORKFLOW_COMPLETE",
                details={
                    "status": result["workflow_status"],
                    "confidence_score": result["confidence_score"],
                    "processing_time": result.get("processing_time_seconds"),
                    "steps_completed": result.get("current_step")
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Workflow execution failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e),
                exc_info=True
            )
            
            # Update state with error
            state["workflow_status"] = "failed"
            state["error_message"] = str(e)
            state["completed_at"] = datetime.now(timezone.utc)
            
            # Audit workflow failure
            await audit(
                event_type=AuditEventType.TICKET_ANALYZED,
                tenant_id=state["tenant_id"],
                resource_type="ticket",
                resource_id=state["ticket_id"],
                action="WORKFLOW_FAILED",
                severity=AuditSeverity.HIGH,
                details={
                    "error": str(e),
                    "current_step": state["current_step"]
                }
            )
            
            return state
    
    async def _classify_ticket_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Classify the ticket to determine processing path."""
        from driftor.agents.nodes.ticket_analyzer import TicketAnalyzer
        
        try:
            state["current_step"] = "classifier"
            
            analyzer = TicketAnalyzer(self.db_session)
            classification = await analyzer.classify_ticket(
                state["ticket_data"],
                state["tenant_id"]
            )
            
            state["ticket_classification"] = classification
            
            logger.info(
                "Ticket classified",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                classification=classification
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Ticket classification failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            state["error_message"] = f"Classification failed: {str(e)}"
            return state
    
    async def _search_similar_tickets_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Search for similar tickets in the tenant's history."""
        from driftor.agents.nodes.similarity_searcher import SimilaritySearcher
        
        try:
            state["current_step"] = "similarity_search"
            
            searcher = SimilaritySearcher(self.db_session)
            similar_tickets = await searcher.find_similar_tickets(
                state["ticket_data"],
                state["tenant_id"],
                limit=5
            )
            
            state["similar_tickets"] = similar_tickets
            
            logger.info(
                "Similar tickets found",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                count=len(similar_tickets)
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Similar ticket search failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            # Non-critical error, continue workflow
            state["similar_tickets"] = []
            return state
    
    async def _retrieve_documentation_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Retrieve relevant documentation from Confluence."""
        from driftor.agents.nodes.doc_retriever import DocumentationRetriever
        
        try:
            state["current_step"] = "doc_retrieval"
            
            retriever = DocumentationRetriever(self.db_session)
            docs = await retriever.find_relevant_docs(
                state["ticket_data"],
                state["tenant_id"],
                limit=3
            )
            
            state["relevant_docs"] = docs
            
            logger.info(
                "Documentation retrieved",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                count=len(docs)
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Documentation retrieval failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            # Non-critical error, continue workflow
            state["relevant_docs"] = []
            return state
    
    async def _map_repository_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Map ticket to relevant Git repository."""
        from driftor.agents.nodes.repo_mapper import RepositoryMapper
        
        try:
            state["current_step"] = "repo_mapper"
            
            mapper = RepositoryMapper(self.db_session)
            repo_info = await mapper.find_relevant_repository(
                state["ticket_data"],
                state["tenant_id"]
            )
            
            state["repository_info"] = repo_info
            
            if repo_info:
                logger.info(
                    "Repository mapped",
                    tenant_id=state["tenant_id"],
                    ticket_id=state["ticket_id"],
                    repository=repo_info.get("name"),
                    provider=repo_info.get("provider")
                )
            else:
                logger.warning(
                    "No repository mapping found",
                    tenant_id=state["tenant_id"],
                    ticket_id=state["ticket_id"]
                )
            
            return state
            
        except Exception as e:
            logger.error(
                "Repository mapping failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            state["repository_info"] = None
            return state
    
    async def _scan_code_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Scan repository code for potential issues."""
        from driftor.agents.nodes.code_scanner import CodeScanner
        
        try:
            state["current_step"] = "code_scanner"
            
            if not state["repository_info"]:
                logger.info(
                    "Skipping code scan - no repository mapped",
                    tenant_id=state["tenant_id"],
                    ticket_id=state["ticket_id"]
                )
                state["code_analysis"] = None
                return state
            
            scanner = CodeScanner(self.db_session)
            analysis = await scanner.analyze_code(
                state["ticket_data"],
                state["repository_info"],
                state["tenant_id"]
            )
            
            state["code_analysis"] = analysis
            
            logger.info(
                "Code analysis completed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                files_analyzed=analysis.get("files_analyzed", 0) if analysis else 0
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Code scanning failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            state["code_analysis"] = None
            return state
    
    async def _generate_fix_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Generate fix suggestions based on analysis."""
        from driftor.agents.nodes.fix_generator import FixGenerator
        
        try:
            state["current_step"] = "fix_generator"
            
            generator = FixGenerator(self.db_session)
            fix_suggestion = await generator.generate_fix(
                ticket_data=state["ticket_data"],
                similar_tickets=state["similar_tickets"],
                code_analysis=state["code_analysis"],
                docs=state["relevant_docs"],
                tenant_id=state["tenant_id"]
            )
            
            state["suggested_fix"] = fix_suggestion
            
            logger.info(
                "Fix suggestion generated",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                has_suggestion=bool(fix_suggestion)
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Fix generation failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            state["suggested_fix"] = None
            return state
    
    async def _calculate_confidence_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Calculate confidence score for the analysis."""
        from driftor.agents.nodes.confidence_scorer import ConfidenceScorer
        
        try:
            state["current_step"] = "confidence_scorer"
            
            scorer = ConfidenceScorer()
            confidence = scorer.calculate_confidence(
                classification=state["ticket_classification"],
                similar_tickets=state["similar_tickets"],
                code_analysis=state["code_analysis"],
                docs=state["relevant_docs"],
                fix_suggestion=state["suggested_fix"]
            )
            
            state["confidence_score"] = confidence
            
            logger.info(
                "Confidence calculated",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                confidence=confidence
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Confidence calculation failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            state["confidence_score"] = 0.0
            return state
    
    async def _send_notification_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Send notification to the assignee."""
        from driftor.agents.nodes.notifier import NotificationSender
        
        try:
            state["current_step"] = "notifier"
            
            # Only send notification if confidence is above threshold
            min_confidence = 0.3  # TODO: Make configurable per tenant
            
            if state["confidence_score"] < min_confidence:
                logger.info(
                    "Skipping notification - confidence too low",
                    tenant_id=state["tenant_id"],
                    ticket_id=state["ticket_id"],
                    confidence=state["confidence_score"],
                    threshold=min_confidence
                )
                state["notification_sent"] = False
                state["workflow_status"] = "completed"
                state["completed_at"] = datetime.now(timezone.utc)
                return state
            
            sender = NotificationSender(self.db_session)
            message_id = await sender.send_analysis_notification(
                assignee_id=state["assignee_id"],
                ticket_data=state["ticket_data"],
                analysis_results={
                    "similar_tickets": state["similar_tickets"],
                    "relevant_docs": state["relevant_docs"],
                    "code_analysis": state["code_analysis"],
                    "suggested_fix": state["suggested_fix"],
                    "confidence_score": state["confidence_score"]
                },
                tenant_id=state["tenant_id"]
            )
            
            state["notification_sent"] = True
            state["message_id"] = message_id
            state["workflow_status"] = "completed"
            state["completed_at"] = datetime.now(timezone.utc)
            
            logger.info(
                "Notification sent",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                message_id=message_id,
                confidence=state["confidence_score"]
            )
            
            return state
            
        except Exception as e:
            logger.error(
                "Notification sending failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e)
            )
            state["notification_sent"] = False
            state["workflow_status"] = "completed"  # Don't fail entire workflow
            state["completed_at"] = datetime.now(timezone.utc)
            return state
    
    async def _handle_error_node(self, state: TicketAnalysisState) -> TicketAnalysisState:
        """Handle workflow errors gracefully."""
        try:
            state["current_step"] = "error_handler"
            state["workflow_status"] = "failed"
            state["completed_at"] = datetime.now(timezone.utc)
            
            logger.error(
                "Workflow failed at error handler",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=state.get("error_message")
            )
            
            # Send error notification to assignee
            error_message = f"⚠️ Driftor encountered an issue analyzing ticket {state['ticket_data'].get('key', state['ticket_id'])}. Our team has been notified."
            
            # TODO: Send error notification via messaging system
            
            return state
            
        except Exception as e:
            logger.critical(
                "Error handler itself failed",
                tenant_id=state["tenant_id"],
                ticket_id=state["ticket_id"],
                error=str(e),
                exc_info=True
            )
            return state
    
    def _route_after_classification(self, state: TicketAnalysisState) -> str:
        """Route workflow based on classification results."""
        classification = state.get("ticket_classification")
        
        if state.get("error_message"):
            return "error"
        
        if not classification:
            return "skip"
        
        # Check if this is a bug ticket worth analyzing
        if classification.get("is_bug", False) and classification.get("confidence", 0) > 0.5:
            return "continue"
        
        return "skip"


# Global workflow instance
_workflow_instance: Optional[TicketAnalysisWorkflow] = None


def get_workflow() -> TicketAnalysisWorkflow:
    """Get global workflow instance."""
    global _workflow_instance
    
    if _workflow_instance is None:
        _workflow_instance = TicketAnalysisWorkflow()
    
    return _workflow_instance


async def process_ticket(ticket_data: Dict[str, any]) -> TicketAnalysisState:
    """Convenience function to process a ticket through the workflow."""
    workflow = get_workflow()
    return await workflow.run_analysis(ticket_data)
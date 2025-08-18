"""
Microsoft Teams integration with adaptive cards and enterprise security.
"""
import json
from typing import Dict, List, Optional, Any
from botbuilder.core import TurnContext, ActivityHandler, MessageFactory, CardFactory
from botbuilder.schema import Activity, ActivityTypes, Attachment, CardAction, ActionTypes
from botbuilder.core.conversation_state import ConversationState
from botbuilder.core.user_state import UserState
from botbuilder.core.memory_storage import MemoryStorage
import httpx
import structlog

from .base import BaseMessagingPlatform, MessagePlatform, MessageCard, MessageResponse, InteractiveButton, ButtonAction
from driftor.integrations.base import IntegrationConfig, WebhookConfig
from driftor.core.rate_limiter import RateLimitType
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class TeamsBot(BaseMessagingPlatform, ActivityHandler):
    """Microsoft Teams bot integration with adaptive cards."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        BaseMessagingPlatform.__init__(self, config, credentials)
        ActivityHandler.__init__(self)
        
        # Set up rate limiting
        config.rate_limit_type = RateLimitType.TEAMS_MESSAGES
        
        self.app_id = self.get_credential("app_id")
        self.app_password = self.get_credential("app_password")
        
        # Bot state management
        memory_storage = MemoryStorage()
        self.conversation_state = ConversationState(memory_storage)
        self.user_state = UserState(memory_storage)
        
        # Store active conversations
        self.active_conversations: Dict[str, Dict[str, Any]] = {}
    
    def _get_platform_type(self) -> MessagePlatform:
        return MessagePlatform.TEAMS
    
    async def test_connection(self) -> bool:
        """Test Teams bot connection."""
        try:
            # Test by making a request to Microsoft Graph API
            headers = await self._get_auth_headers()
            
            response = await self._make_request(
                "GET",
                "https://graph.microsoft.com/v1.0/me",
                headers=headers,
                identifier="test_connection"
            )
            
            return response.success
            
        except Exception as e:
            logger.error("Teams connection test failed", error=str(e))
            return False
    
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get Teams webhook configuration."""
        return WebhookConfig(
            endpoint_url=f"{self.config.api_base_url}/webhooks/teams",
            secret=self.get_credential("webhook_secret", ""),
            events=["message", "invoke", "conversationUpdate"]
        )
    
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Teams webhook signature."""
        # Teams uses JWT verification instead of HMAC
        # This would require validating the JWT token in the Authorization header
        # For now, we'll implement basic verification
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return True  # Allow if no secret configured
        
        return self.verify_webhook_signature_hmac(payload, signature, webhook_secret, "sha256")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Microsoft Graph API."""
        # In production, this would use OAuth2 flow to get access token
        # For now, we'll use bot credentials
        return {
            "Authorization": f"Bearer {self.app_password}",
            "Content-Type": "application/json"
        }
    
    async def send_message(
        self, 
        user_id: str, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> MessageResponse:
        """Send a simple text message."""
        try:
            await self._check_rate_limit(user_id)
            
            # Create message activity
            activity = MessageFactory.text(message)
            
            # Send via proactive message
            response_id = await self._send_proactive_message(user_id, activity, thread_id)
            
            return MessageResponse(
                success=True,
                message_id=response_id,
                thread_id=thread_id,
                platform=self.platform.value
            )
            
        except Exception as e:
            logger.error(
                "Failed to send Teams message",
                user_id=user_id,
                error=str(e)
            )
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    async def send_card(
        self, 
        user_id: str, 
        card: MessageCard,
        thread_id: Optional[str] = None
    ) -> MessageResponse:
        """Send an adaptive card message."""
        try:
            await self._check_rate_limit(user_id)
            
            # Create adaptive card
            adaptive_card = self._create_adaptive_card(card)
            
            # Create activity with card attachment
            activity = MessageFactory.attachment(adaptive_card)
            
            # Send via proactive message
            response_id = await self._send_proactive_message(user_id, activity, thread_id)
            
            return MessageResponse(
                success=True,
                message_id=response_id,
                thread_id=thread_id,
                platform=self.platform.value
            )
            
        except Exception as e:
            logger.error(
                "Failed to send Teams card",
                user_id=user_id,
                error=str(e)
            )
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    async def handle_interaction(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle adaptive card button interactions."""
        try:
            activity = Activity().deserialize(interaction_data)
            
            if activity.type == ActivityTypes.invoke:
                # Handle adaptive card invoke
                invoke_value = activity.value
                action = invoke_value.get("action")
                ticket_key = invoke_value.get("ticket_key", "")
                user_id = activity.from_property.id
                
                logger.info(
                    "Teams interaction received",
                    action=action,
                    ticket_key=ticket_key,
                    user_id=user_id
                )
                
                # Route to appropriate handler
                if action == ButtonAction.ELABORATE_FIX.value:
                    return await self._handle_elaborate_fix(activity, ticket_key)
                elif action == ButtonAction.CHAT_WITH_DRIFTOR.value:
                    return await self._handle_chat_request(activity, ticket_key)
                elif action == ButtonAction.MARK_HELPFUL.value:
                    return await self._handle_feedback(activity, ticket_key, True)
                elif action == ButtonAction.MARK_UNHELPFUL.value:
                    return await self._handle_feedback(activity, ticket_key, False)
                elif action == ButtonAction.VIEW_SIMILAR_TICKETS.value:
                    return await self._handle_view_similar_tickets(activity, ticket_key)
                elif action == ButtonAction.VIEW_DOCUMENTATION.value:
                    return await self._handle_view_documentation(activity, ticket_key)
                else:
                    return {"status": "unknown_action", "action": action}
            
            return {"status": "handled"}
            
        except Exception as e:
            logger.error("Failed to handle Teams interaction", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def start_conversation(
        self, 
        user_id: str, 
        initial_message: str
    ) -> MessageResponse:
        """Start a new conversation thread."""
        try:
            # Create conversation thread
            conversation_id = f"driftor_{user_id}_{int(datetime.now().timestamp())}"
            
            # Store conversation context
            self.active_conversations[conversation_id] = {
                "user_id": user_id,
                "started_at": datetime.now().isoformat(),
                "messages": [{"role": "assistant", "content": initial_message}]
            }
            
            # Send initial message
            response = await self.send_message(user_id, initial_message, conversation_id)
            response.thread_id = conversation_id
            
            return response
            
        except Exception as e:
            logger.error("Failed to start Teams conversation", error=str(e))
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    def _create_adaptive_card(self, card: MessageCard) -> Attachment:
        """Create adaptive card from MessageCard."""
        # Build adaptive card JSON
        adaptive_card_json = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": []
        }
        
        # Add title
        if card.title:
            adaptive_card_json["body"].append({
                "type": "TextBlock",
                "text": card.title,
                "size": "Large",
                "weight": "Bolder",
                "color": self._map_color_to_teams(card.color)
            })
        
        # Add subtitle
        if card.subtitle:
            adaptive_card_json["body"].append({
                "type": "TextBlock",
                "text": card.subtitle,
                "size": "Medium",
                "color": "Accent",
                "spacing": "None"
            })
        
        # Add main text
        if card.text:
            adaptive_card_json["body"].append({
                "type": "TextBlock",
                "text": card.text,
                "wrap": True,
                "spacing": "Medium"
            })
        
        # Add facts as a fact set
        if card.facts:
            fact_set = {
                "type": "FactSet",
                "facts": [
                    {"title": fact["name"], "value": fact["value"]}
                    for fact in card.facts
                ],
                "spacing": "Medium"
            }
            adaptive_card_json["body"].append(fact_set)
        
        # Add thumbnail
        if card.thumbnail_url:
            adaptive_card_json["body"].insert(0, {
                "type": "Image",
                "url": card.thumbnail_url,
                "size": "Small",
                "horizontalAlignment": "Right"
            })
        
        # Add buttons as actions
        if card.buttons:
            adaptive_card_json["actions"] = []
            for button in card.buttons:
                action = {
                    "type": "Action.Submit",
                    "title": button.text,
                    "data": {
                        "action": button.action.value,
                        "ticket_key": button.value or "",
                        "button_id": button.id
                    }
                }
                
                # Handle URL buttons
                if button.url:
                    action = {
                        "type": "Action.OpenUrl",
                        "title": button.text,
                        "url": button.url
                    }
                
                adaptive_card_json["actions"].append(action)
        
        # Create attachment
        return CardFactory.adaptive_card(adaptive_card_json)
    
    def _map_color_to_teams(self, color: str) -> str:
        """Map generic color to Teams color."""
        color_map = {
            "good": "Good",
            "warning": "Warning", 
            "attention": "Attention",
            "accent": "Accent",
            "default": "Default"
        }
        return color_map.get(color, "Default")
    
    async def _send_proactive_message(
        self, 
        user_id: str, 
        activity: Activity,
        thread_id: Optional[str] = None
    ) -> str:
        """Send proactive message to user."""
        try:
            # In production, this would use Bot Framework's proactive messaging
            # For now, we'll simulate with a direct API call
            
            headers = await self._get_auth_headers()
            
            message_data = {
                "type": "message",
                "from": {"id": self.app_id, "name": "Driftor"},
                "conversation": {"id": thread_id or f"user_{user_id}"},
                "recipient": {"id": user_id},
                "text": activity.text if hasattr(activity, 'text') else "",
                "attachments": activity.attachments if hasattr(activity, 'attachments') else []
            }
            
            # Use Microsoft Graph API to send message
            response = await self._make_request(
                "POST",
                f"https://graph.microsoft.com/v1.0/chats/{thread_id or user_id}/messages",
                headers=headers,
                json_data=message_data,
                identifier=f"send_message_{user_id}"
            )
            
            if response.success and response.data:
                return response.data.get("id", "")
            
            return ""
            
        except Exception as e:
            logger.error("Failed to send proactive Teams message", error=str(e))
            return ""
    
    async def _handle_elaborate_fix(self, activity: Activity, ticket_key: str) -> Dict[str, Any]:
        """Handle elaborate fix button click."""
        try:
            # TODO: Get detailed fix explanation from LLM
            detailed_fix = f"Here's a more detailed explanation for {ticket_key}:\n\n" \
                          "1. The issue appears to be in the error handling logic\n" \
                          "2. Consider adding null checks before accessing properties\n" \
                          "3. Implement proper exception handling\n\n" \
                          "Would you like me to provide specific code examples?"
            
            # Send detailed response
            await self.send_message(
                activity.from_property.id,
                detailed_fix,
                activity.conversation.id
            )
            
            return {"status": "elaborated", "ticket_key": ticket_key}
            
        except Exception as e:
            logger.error("Failed to handle elaborate fix", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_chat_request(self, activity: Activity, ticket_key: str) -> Dict[str, Any]:
        """Handle chat with Driftor request."""
        try:
            chat_message = f"Hi! I'm here to help with {ticket_key}. " \
                          "What specific questions do you have about this issue? " \
                          "I can help with:\n\n" \
                          "• Code analysis and debugging\n" \
                          "• Similar issue research\n" \
                          "• Best practice recommendations\n" \
                          "• Documentation search\n\n" \
                          "Just ask me anything!"
            
            # Start conversation
            response = await self.start_conversation(
                activity.from_property.id,
                chat_message
            )
            
            return {
                "status": "chat_started", 
                "ticket_key": ticket_key,
                "conversation_id": response.thread_id
            }
            
        except Exception as e:
            logger.error("Failed to handle chat request", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_feedback(
        self, 
        activity: Activity, 
        ticket_key: str, 
        helpful: bool
    ) -> Dict[str, Any]:
        """Handle feedback button clicks."""
        try:
            feedback_message = "Thank you for your feedback! " \
                             f"Your input helps improve Driftor's analysis quality."
            
            if not helpful:
                feedback_message += "\n\nWhat could I have done better? " \
                                  "You can chat with me to provide more specific feedback."
            
            await self.send_message(
                activity.from_property.id,
                feedback_message,
                activity.conversation.id
            )
            
            # TODO: Store feedback in database for analysis improvement
            
            return {
                "status": "feedback_received",
                "ticket_key": ticket_key,
                "helpful": helpful
            }
            
        except Exception as e:
            logger.error("Failed to handle feedback", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_view_similar_tickets(
        self, 
        activity: Activity, 
        ticket_key: str
    ) -> Dict[str, Any]:
        """Handle view similar tickets request."""
        try:
            # TODO: Get similar tickets from analysis results
            similar_message = f"Here are similar issues to {ticket_key}:\n\n" \
                            "• **PROJ-123**: Similar null pointer exception\n" \
                            "• **PROJ-124**: Related API timeout issue\n" \
                            "• **PROJ-125**: Same component error pattern\n\n" \
                            "Would you like detailed analysis of any of these?"
            
            await self.send_message(
                activity.from_property.id,
                similar_message,
                activity.conversation.id
            )
            
            return {"status": "similar_tickets_shown", "ticket_key": ticket_key}
            
        except Exception as e:
            logger.error("Failed to handle view similar tickets", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_view_documentation(
        self, 
        activity: Activity, 
        ticket_key: str
    ) -> Dict[str, Any]:
        """Handle view documentation request."""
        try:
            # TODO: Get relevant documentation from analysis results
            docs_message = f"Relevant documentation for {ticket_key}:\n\n" \
                          "📚 **Error Handling Best Practices**\n" \
                          "https://docs.company.com/error-handling\n\n" \
                          "📚 **API Integration Guide**\n" \
                          "https://docs.company.com/api-guide\n\n" \
                          "📚 **Troubleshooting Common Issues**\n" \
                          "https://docs.company.com/troubleshooting"
            
            await self.send_message(
                activity.from_property.id,
                docs_message,
                activity.conversation.id
            )
            
            return {"status": "documentation_shown", "ticket_key": ticket_key}
            
        except Exception as e:
            logger.error("Failed to handle view documentation", error=str(e))
            return {"status": "error", "error": str(e)}


from datetime import datetime
"""
Microsoft Teams Bot Adapter and configuration.
"""
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    UserState,
    MemoryStorage,
    TurnContext,
    ActivityHandler,
    MessageFactory,
)
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class TeamsBot(ActivityHandler):
    """Main Teams bot activity handler."""
    
    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        self.conversation_state = conversation_state
        self.user_state = user_state
    
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle incoming messages from Teams."""
        user_message = turn_context.activity.text.strip()
        user_id = turn_context.activity.from_property.id
        
        logger.info(f"Received message from {user_id}: {user_message}")
        
        # Route message based on content
        if user_message.lower().startswith("help"):
            await self._send_help_message(turn_context)
        elif user_message.lower().startswith("status"):
            await self._send_status_message(turn_context)
        elif "elaborate" in user_message.lower():
            await self._handle_elaborate_request(turn_context)
        else:
            await self._handle_general_query(turn_context, user_message)
        
        # Save conversation state
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)
    
    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ) -> None:
        """Handle new members added to the conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
    
    async def _send_welcome_message(self, turn_context: TurnContext) -> None:
        """Send welcome message to new users."""
        welcome_text = (
            "🤖 **Welcome to Developer Workflow Bot!**\n\n"
            "I help developers by automatically analyzing Jira tickets and providing:\n"
            "• Similar issue analysis\n"
            "• Related documentation links\n" 
            "• Code analysis and fix suggestions\n\n"
            "Type `help` for more commands."
        )
        await turn_context.send_activity(MessageFactory.text(welcome_text))
    
    async def _send_help_message(self, turn_context: TurnContext) -> None:
        """Send help message with available commands."""
        help_text = (
            "**Available Commands:**\n\n"
            "• `status` - Check bot status and integrations\n"
            "• `elaborate [ticket]` - Get detailed analysis for a specific ticket\n"
            "• `help` - Show this help message\n\n"
            "I'll also automatically notify you when new tickets are assigned!"
        )
        await turn_context.send_activity(MessageFactory.text(help_text))
    
    async def _send_status_message(self, turn_context: TurnContext) -> None:
        """Send bot status and integration information."""
        status_text = (
            "**Bot Status:** ✅ Online\n\n"
            "**Active Integrations:**\n"
            "• Jira: Connected\n"
            "• Confluence: Connected\n"
            "• GitHub: Connected\n\n"
            "Ready to analyze tickets!"
        )
        await turn_context.send_activity(MessageFactory.text(status_text))
    
    async def _handle_elaborate_request(self, turn_context: TurnContext) -> None:
        """Handle requests for ticket elaboration."""
        message = turn_context.activity.text
        
        # Extract ticket key from message (simple regex would go here)
        # For now, send a placeholder response
        response_text = (
            "🔍 **Detailed Analysis Request**\n\n"
            "I'm analyzing the ticket for you... This would include:\n"
            "• Deep code analysis\n"
            "• Step-by-step fix instructions\n"
            "• Potential side effects\n"
            "• Testing recommendations\n\n"
            "*(Full implementation coming soon)*"
        )
        await turn_context.send_activity(MessageFactory.text(response_text))
    
    async def _handle_general_query(self, turn_context: TurnContext, message: str) -> None:
        """Handle general queries and chat."""
        response_text = (
            f"I received your message: '{message}'\n\n"
            "I'm designed to help with Jira ticket analysis. "
            "Type `help` to see what I can do!"
        )
        await turn_context.send_activity(MessageFactory.text(response_text))


class TeamsAdapter:
    """Teams bot adapter wrapper."""
    
    def __init__(self):
        # Bot Framework settings
        settings_obj = BotFrameworkAdapterSettings(
            app_id=settings.MICROSOFT_APP_ID,
            app_password=settings.MICROSOFT_APP_PASSWORD,
        )
        
        # Create adapter
        self.adapter = BotFrameworkAdapter(settings_obj)
        
        # Create state storage
        memory_storage = MemoryStorage()
        self.conversation_state = ConversationState(memory_storage)
        self.user_state = UserState(memory_storage)
        
        # Create bot instance
        self.bot = TeamsBot(self.conversation_state, self.user_state)
        
        # Error handler
        async def on_error(context: TurnContext, error: Exception):
            logger.error(f"Bot error: {error}")
            await context.send_activity(
                MessageFactory.text("Sorry, an error occurred. Please try again.")
            )
        
        self.adapter.on_turn_error = on_error
    
    async def process_activity(self, activity: dict, auth_header: str = "") -> dict:
        """Process incoming activity from Teams."""
        try:
            # Convert dict to Activity object
            activity_obj = Activity.deserialize(activity)
            
            # Process the activity
            response = await self.adapter.process_activity(
                activity_obj, auth_header, self.bot.on_turn
            )
            
            return response
        except Exception as e:
            logger.error(f"Error processing activity: {e}")
            raise
    
    async def send_proactive_message(
        self, 
        user_id: str, 
        message: str, 
        service_url: str,
        conversation_id: Optional[str] = None
    ) -> None:
        """Send proactive message to a Teams user."""
        try:
            # Create conversation reference for proactive messaging
            # This would need proper implementation based on stored conversation references
            logger.info(f"Sending proactive message to {user_id}: {message}")
            
            # TODO: Implement actual proactive messaging
            # This requires storing conversation references when users first interact
            
        except Exception as e:
            logger.error(f"Error sending proactive message: {e}")
            raise
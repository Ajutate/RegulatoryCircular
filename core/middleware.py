from typing import Callable
from langchain_core.messages import SystemMessage
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse

from core.skill_loader import load_skill_index, read_skill
from core.logger import get_logger

logger = get_logger(__name__)

class SkillMiddleware(AgentMiddleware):
    """Middleware that injects skill descriptions into the system prompt."""

    # Register the read_skill tool as a class variable
    tools = [read_skill]

    def __init__(self):
        """Initialize and generate the skills prompt from SKILLS."""
        super().__init__()
        # Build skills prompt from the skill_index
        index = load_skill_index()
        skills_list = []
        for skill in index:
            skills_list.append(
                f"- **{skill['name']}**: {skill['description']}"
            )
        self.skills_prompt = "\n".join(skills_list)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Inject skill descriptions into system prompt."""
        # Build the skills addendum
        skills_addendum = (
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "Use the read_skill tool when you need detailed information "
            "about handling a specific type of request. Pass the exact skill name to read_skill."
        )

        # Assuming the state holds the messages list and the first message is SystemMessage
        messages = request.state.get("messages", [])
        new_messages = list(messages)
        
        for i, msg in enumerate(new_messages):
            if isinstance(msg, SystemMessage) or getattr(msg, 'type', '') == 'system':
                old_content = msg.content if hasattr(msg, 'content') else msg.get("content", "")
                new_sys_msg = SystemMessage(content=old_content + skills_addendum)
                new_messages[i] = new_sys_msg
                logger.info(f"\n\n--- Final System Prompt (Post-Middleware) ---\n{new_sys_msg.content}\n---------------------------------------------\n")
                break
                
        request.state["messages"] = new_messages
        return handler(request)

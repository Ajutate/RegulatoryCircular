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
        # Build concise skills prompt from the skill_index
        index = load_skill_index()
        skills_list = []
        for skill in index:
            desc = skill.get("description", "")
            if "Use when the paragraph mentions" in desc:
                core = desc.split("Use when the paragraph mentions")[1].split(".")[0].strip()
                skills_list.append(f"- **{skill['name']}**: Covers {core}")
            else:
                skills_list.append(f"- **{skill['name']}**: {desc.split('.')[0].strip()}")
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
            "To load the taxonomy values (business units, themes, levels, control objectives) for any domain above, "
            "call the `read_skill` tool with the skill name (e.g. `read_skill(skill_name='treasury-front-office')`). "
            "Note: `read_skill` is the ONLY tool available. Once you receive the taxonomy, respond with the final JSON."
        )

        # request.messages holds the messages passed to the model
        new_messages = list(request.messages)
        modified = False
        
        for i, msg in enumerate(new_messages):
            if isinstance(msg, SystemMessage) or getattr(msg, "type", "") == "system":
                old_content = msg.content if hasattr(msg, "content") else str(msg)
                if "## Available Skills" not in old_content:
                    new_sys_msg = SystemMessage(content=old_content + skills_addendum)
                    new_messages[i] = new_sys_msg
                    modified = True
                    logger.info("SkillMiddleware injected available skills catalog into SystemMessage.")
                break
                
        if modified:
            return handler(request.override(messages=new_messages))
            
        # Fallback for request.system_prompt attribute if system prompt is configured separately
        if request.system_prompt and "## Available Skills" not in request.system_prompt:
            new_sys = request.system_prompt + skills_addendum
            logger.info("SkillMiddleware injected available skills catalog into request.system_prompt.")
            return handler(request.override(system_prompt=new_sys))

        return handler(request)

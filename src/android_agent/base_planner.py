from typing import List, Optional, Union, Dict, Any
from .android_action import AndroidAction
from .android_state import AndroidState
from .android_step import AndroidStep

class ActionPlanner:
    """Abstract base class for action planners.
    
    This class defines the interface that all action planners must implement.
    """
    
    def plan_action(
        self,
        goal: str,
        additional_context: Optional[Union[str, Dict[str, Any]]] = None,
        additional_instructions: Optional[List[str]] = None,
        current_state: Optional[AndroidState] = None,
        session_history: Optional[List[AndroidStep]] = None
    ) -> AndroidAction:
        """Plan next action based on current state and goal.
        
        Args:
            goal: The goal to achieve
            additional_context: Extra context information
            additional_instructions: Extra instructions
            current_state: Current device state
            session_history: History of previous actions and states
            
        Returns:
            The next action to perform
        """
        raise NotImplementedError("Subclasses must implement plan_action") 
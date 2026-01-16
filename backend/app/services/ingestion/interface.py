from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.schemas.proposal import Operation

class IngestionStrategy(ABC):
    @abstractmethod
    async def process(self, content: Any, **kwargs) -> List[Operation]:
        """
        Process source content and return a list of Graph Operations.
        
        Args:
            content: The input content (text, file path, or structured data).
            **kwargs: Additional context (e.g., domain_context, tenant_id).
            
        Returns:
            List[Operation]: A list of operations to be included in a Proposal.
        """
        pass

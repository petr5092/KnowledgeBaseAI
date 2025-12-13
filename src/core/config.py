from pydantic import BaseModel, Field
import os

class Settings(BaseModel):
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    neo4j_uri: str = Field(default=os.getenv("NEO4J_URI", ""))
    neo4j_user: str = Field(default=os.getenv("NEO4J_USER", ""))
    neo4j_password: str = Field(default=os.getenv("NEO4J_PASSWORD", ""))
    chroma_host: str = Field(default=os.getenv("CHROMA_HOST", "chroma"))
    chroma_port: int = Field(default=int(os.getenv("CHROMA_PORT", "8000")))
    prometheus_enabled: bool = Field(default=os.getenv("PROMETHEUS_ENABLED", "false").lower() == "true")

settings = Settings()

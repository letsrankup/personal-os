"""Agent registry: agent_key -> agent instance.

All 11 agents are implemented for real (master, tasks, reporting in
Phase 3–5; research, communication, clients, business, developer, finance,
marketing, projects in Phase 6). Agents never fabricate results: when a
capability needs an unconnected integration they return FAILED with the
exact reason.
"""
from .base import BaseAgent, NotImplementedAgent
from .business_agent import BusinessAgent
from .clients_agent import ClientsAgent
from .communication_agent import CommunicationAgent
from .developer_agent import DeveloperAgent
from .finance_agent import FinanceAgent
from .marketing_agent import MarketingAgent
from .master_agent import MasterAgent
from .projects_agent import ProjectsAgent
from .reporting_agent import ReportingAgent
from .research_agent import ResearchAgent
from .tasks_agent import TasksAgent

REGISTRY: dict[str, BaseAgent] = {
    "master": MasterAgent(),
    "research": ResearchAgent(),
    "tasks": TasksAgent(),
    "communication": CommunicationAgent(),
    "clients": ClientsAgent(),
    "business": BusinessAgent(),
    "developer": DeveloperAgent(),
    "finance": FinanceAgent(),
    "marketing": MarketingAgent(),
    "projects": ProjectsAgent(),
    "reporting": ReportingAgent(),
}


def get_agent(agent_key: str) -> BaseAgent:
    return REGISTRY.get(agent_key) or NotImplementedAgent(agent_key, agent_key)

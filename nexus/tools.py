"""The complete model-facing tool registry; no dynamic tool loading."""
from .validation import ACTIONS

def tool(name: str, description: str, properties: dict[str, str]) -> dict:
    return {
        "type": "function", "name": name, "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {k: {"type": v, "description": ("YYYY-MM-DD or empty string" if k == "due_date" else "Use empty string for unspecified optional fields" if k in ("time", "location", "details") else k)} for k, v in properties.items()},
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOLS = [
    tool("create_project", "Propose saving a project record", {"title": "string", "goal": "string"}),
    tool("create_task", "Propose creating a task", {"title": "string", "owner": "string", "due_date": "string", "priority": "string"}),
    tool("set_task_status", "Propose marking a task todo, doing or done", {"task_id": "integer", "status": "string"}),
    tool("assign_task", "Propose changing the responsible person for a task", {"task_id": "integer", "owner": "string"}),
    tool("create_event", "Propose creating a local event", {"title": "string", "day": "string", "time": "string", "location": "string", "details": "string"}),
    tool("create_note", "Propose saving a meeting note", {"title": "string", "body": "string"}),
    tool("remember", "Propose recording a non-sensitive workspace preference or fact", {"key": "string", "value": "string"}),
]

TOOLS.extend([
    tool("forget", "Propose deleting a saved fact", {"key": "string"}),
    {
        "type": "function", "name": "execute_plan",
        "description": "Propose 1 to 5 local actions as an atomic plan; never executes before human approval. Each arguments_json follows that action's schema.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"steps": {"type": "array", "minItems": 1, "maxItems": 5,
                "items": {"type": "object", "properties": {
                    "name": {"type": "string", "enum": sorted(ACTIONS - {"execute_plan"})},
                    "arguments_json": {"type": "string"}},
                    "required": ["name", "arguments_json"], "additionalProperties": False}}},
            "required": ["steps"], "additionalProperties": False,
        },
    },
])
assert {item["name"] for item in TOOLS} == ACTIONS

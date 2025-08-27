#!/usr/bin/env python3

import os
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional

from fastmcp import FastMCP
from dotenv import load_dotenv
from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request
from ticktick_client import TickTickClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OAuth Proxy setup for TickTick (non-DCR provider)
def create_oauth_proxy():
    """Create OAuth Proxy for TickTick if credentials are available"""
    try:
        from fastmcp.server.auth import OAuthProxy
    except ImportError:
        print("⚠️  OAuthProxy not available in this FastMCP version")
        return None
    
    client_id = os.getenv("TICKTICK_CLIENT_ID")
    client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
    # Use the fly.io app URL for production
    app_name = os.getenv("FLY_APP_NAME", "ticktick-mcp")
    base_url = os.getenv("FASTMCP_SERVER_AUTH_OAUTH_PROXY_BASE_URL", f"https://{app_name}.fly.dev")
    
    if not (client_id and client_secret):
        print("⚠️  No TickTick OAuth credentials found. Set TICKTICK_CLIENT_ID and TICKTICK_CLIENT_SECRET")
        return None
    
    print(f"✅ Creating OAuth Proxy for TickTick (client_id: {client_id[:8]}...)")
    print(f"🌐 Base URL: {base_url}")
    
    # Minimal token verifier for TickTick opaque tokens
    from fastmcp.server.auth.oauth_proxy import TokenVerifier, AccessToken

    class TickTickTokenVerifier(TokenVerifier):
        def __init__(self, client_id: str, resource_server_url: str | None = None):
            super().__init__(resource_server_url=resource_server_url, required_scopes=[])
            self._client_id = client_id

        async def verify_token(self, token: str) -> AccessToken | None:
            return AccessToken(token=token, client_id=self._client_id, scopes=[], expires_at=None, resource=str(self.resource_server_url) if self.resource_server_url else None)
    
    return OAuthProxy(
        upstream_authorization_endpoint="https://ticktick.com/oauth/authorize",
        upstream_token_endpoint="https://ticktick.com/oauth/token",
        upstream_client_id=client_id,
        upstream_client_secret=client_secret,
        token_verifier=TickTickTokenVerifier(client_id=client_id, resource_server_url=base_url),
        base_url=base_url,
        redirect_path="/auth/callback",
        allowed_client_redirect_uris=["http://localhost:*", "http://127.0.0.1:*", "https://*.fly.dev"],
    )

# Create FastMCP server with OAuth Proxy if available
oauth_proxy = create_oauth_proxy()
if oauth_proxy:
    print("🔐 Starting MCP server with OAuth Proxy for TickTick")
    mcp = FastMCP("ticktick", auth=oauth_proxy)
else:
    print("🔓 Starting MCP server without OAuth (manual token required)")
    mcp = FastMCP("ticktick")

# Initialize TickTick client
ticktick = None

def get_auth_token():
    """Get OAuth access token from FastMCP auth context or fallback to environment."""
    # Try to get token from FastMCP OAuth identity (when OAuth Proxy is used)
    try:
        from fastmcp.server.dependencies import get_identity
        identity = get_identity()
        if identity and hasattr(identity, 'access_token'):
            return identity.access_token
    except Exception:
        # get_identity not available or no identity context
        pass
    
    # Fallback to environment variables for testing
    return os.getenv("TICKTICK_AUTH_TOKEN") or os.getenv("AUTH_TOKEN")

def initialize_client():
    """Initialize the TickTick client with OAuth token from auth context or environment."""
    global ticktick
    
    auth_token = get_auth_token()
    if not auth_token:
        return False
    
    try:
        ticktick = TickTickClient(auth_token)
        return True
    except Exception as e:
        logging.error(f"Failed to initialize TickTick client: {e}")
        return False

# Utility functions for formatting
def format_task(task: Dict) -> str:
    """Format a task object from TickTick for better display."""
    formatted = f"Title: {task.get('title', 'No title')}\n"
    formatted += f"ID: {task.get('id', 'No ID')}\n"
    formatted += f"Project ID: {task.get('projectId', 'No project')}\n"
    
    # Add completion status
    status = task.get('status', 0)
    formatted += f"Status: {'✓ Completed' if status == 2 else '□ Incomplete'}\n"
    
    # Add priority if available
    priority = task.get('priority', 0)
    if priority > 0:
        priority_text = {1: "Low", 3: "Medium", 5: "High"}.get(priority, f"Priority {priority}")
        formatted += f"Priority: {priority_text}\n"
    
    # Add content if available
    if task.get('content'):
        formatted += f"Content: {task.get('content')}\n"
    
    # Add due date if available
    if task.get('dueDate'):
        formatted += f"Due Date: {task.get('dueDate')}\n"
    
    # Add start date if available  
    if task.get('startDate'):
        formatted += f"Start Date: {task.get('startDate')}\n"
    
    # Add tags if available
    tags = task.get('tags', [])
    if tags:
        formatted += f"Tags: {', '.join(tags)}\n"
    
    # Add subtasks if available
    items = task.get('items', [])
    if items:
        formatted += f"\nSubtasks ({len(items)}):\n"
        for i, item in enumerate(items, 1):
            status = "✓" if item.get('status') == 1 else "□"
            formatted += f"{i}. [{status}] {item.get('title', 'No title')}\n"
    
    return formatted

def format_project(project: Dict) -> str:
    """Format a project into a human-readable string."""
    formatted = f"Name: {project.get('name', 'No name')}\n"
    formatted += f"ID: {project.get('id', 'No ID')}\n"
    
    if project.get('color'):
        formatted += f"Color: {project.get('color')}\n"
    
    if project.get('viewMode'):
        formatted += f"View Mode: {project.get('viewMode')}\n"
    
    if 'closed' in project:
        formatted += f"Closed: {'Yes' if project.get('closed') else 'No'}\n"
    
    if project.get('kind'):
        formatted += f"Kind: {project.get('kind')}\n"
    
    return formatted

# Core TickTick Tools

@mcp.tool
async def get_projects() -> str:
    """Get all projects from TickTick."""
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your AUTH_TOKEN environment variable."
    
    try:
        projects = ticktick.get_projects()
        if 'error' in projects:
            return f"Error fetching projects: {projects['error']}"
        
        if not projects:
            return "No projects found."
        
        result = f"Found {len(projects)} projects:\n\n"
        for i, project in enumerate(projects, 1):
            result += f"Project {i}:\n{format_project(project)}\n"
        
        return result
        
    except Exception as e:
        return f"Error getting projects: {str(e)}"

@mcp.tool
async def get_project_tasks(project_id: str) -> str:
    """
    Get all tasks in a specific project.
    
    Args:
        project_id: The ID of the project to get tasks from
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your AUTH_TOKEN environment variable."
    
    try:
        tasks = ticktick.get_project_tasks(project_id)
        if 'error' in tasks:
            return f"Error fetching tasks: {tasks['error']}"
        
        if not tasks:
            return f"No tasks found in project {project_id}."
        
        result = f"Found {len(tasks)} tasks in project {project_id}:\n\n"
        for i, task in enumerate(tasks, 1):
            result += f"Task {i}:\n{format_task(task)}\n"
        
        return result
        
    except Exception as e:
        return f"Error getting project tasks: {str(e)}"

@mcp.tool
async def get_all_tasks() -> str:
    """Get all tasks from TickTick. Ignores closed projects."""
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your AUTH_TOKEN environment variable."
    
    try:
        tasks = ticktick.get_all_tasks()
        if 'error' in tasks:
            return f"Error fetching tasks: {tasks['error']}"
        
        if not tasks:
            return "No tasks found."
        
        result = f"Found {len(tasks)} tasks:\n\n"
        for i, task in enumerate(tasks, 1):
            result += f"Task {i}:\n{format_task(task)}\n"
        
        return result
        
    except Exception as e:
        return f"Error getting all tasks: {str(e)}"

@mcp.tool
async def search_tasks(search_term: str) -> str:
    """
    Search for tasks in TickTick by title, content, or subtask titles.
    
    Args:
        search_term: The term to search for in tasks
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your AUTH_TOKEN environment variable."
    
    try:
        tasks = ticktick.get_all_tasks()
        if 'error' in tasks:
            return f"Error fetching tasks: {tasks['error']}"
        
        # Filter tasks based on search term
        matching_tasks = []
        search_lower = search_term.lower()
        
        for task in tasks:
            # Search in title and content
            if (search_lower in task.get('title', '').lower() or 
                search_lower in task.get('content', '').lower()):
                matching_tasks.append(task)
                continue
                
            # Search in subtasks
            items = task.get('items', [])
            for item in items:
                if search_lower in item.get('title', '').lower():
                    matching_tasks.append(task)
                    break
        
        if not matching_tasks:
            return f"No tasks found matching '{search_term}'."
        
        result = f"Found {len(matching_tasks)} tasks matching '{search_term}':\n\n"
        for i, task in enumerate(matching_tasks, 1):
            result += f"Task {i}:\n{format_task(task)}\n"
        
        return result
        
    except Exception as e:
        return f"Error searching tasks: {str(e)}"

@mcp.tool
async def get_tasks_due_today() -> str:
    """Get all tasks from TickTick that are due today."""
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your AUTH_TOKEN environment variable."
    
    try:
        tasks = ticktick.get_all_tasks()
        if 'error' in tasks:
            return f"Error fetching tasks: {tasks['error']}"
        
        today = datetime.now(timezone.utc).date()
        due_today = []
        
        for task in tasks:
            due_date_str = task.get('dueDate')
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')).date()
                    if due_date == today:
                        due_today.append(task)
                except ValueError:
                    continue
        
        if not due_today:
            return "No tasks are due today."
        
        result = f"Found {len(due_today)} tasks due today:\n\n"
        for i, task in enumerate(due_today, 1):
            result += f"Task {i}:\n{format_task(task)}\n"
        
        return result
        
    except Exception as e:
        return f"Error getting tasks due today: {str(e)}"

@mcp.tool
async def ping() -> str:
    """Ping the server to check if it's responsive"""
    return "pong"

@mcp.tool
async def test_ticktick_connection() -> str:
    """Test the TickTick API connection"""
    if not ticktick:
        if not initialize_client():
            return "❌ Failed to initialize TickTick client. Please check your AUTH_TOKEN environment variable."
    
    try:
        projects = ticktick.get_projects()
        if 'error' in projects:
            return f"❌ TickTick API error: {projects['error']}"
        
        return f"✅ TickTick connection successful! Found {len(projects)} projects."
        
    except Exception as e:
        return f"❌ TickTick connection failed: {str(e)}"

def create_app():
    """Create the ASGI app for fly.io deployment"""
    return mcp.http_app(path='/sse', transport="sse")

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (fly.io sets this)
    port = int(os.getenv("PORT", 8000))
    
    print(f"Starting TickTick MCP Server on fly.io...")
    print(f"MCP SSE endpoint will be at: http://0.0.0.0:{port}/sse")
    print("SSE endpoint available for mcp-remote at /sse")
    
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

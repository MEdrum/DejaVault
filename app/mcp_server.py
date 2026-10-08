"""MCP (Model Context Protocol) server for DejaVault.

Exposes the MemoryService as MCP tools over streamable HTTP, so coding
agents can use DejaVault as a remote MCP server without a local bridge.

The MCP layer is a thin adapter over the same MemoryService instance
used by the REST API — no business logic is duplicated.

Tool descriptions are written for LLM consumption: they explain what
the tool does, when to use it, how to call it, and what the response
looks like.
"""

import logging

from mcp.server.mcpserver import MCPServer

from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

# Separator between multi-result blocks. A line of 40 '=' characters is
# unambiguous — it cannot appear in normal markdown content.
RESULT_SEPARATOR = "=" * 40


def _format_result_block(score: float, file_path: str, content: str, max_chars: int) -> str:
    """Format a single search result with an explicit EOF marker.

    The EOF marker makes the block boundary unambiguous even when the
    content contains blank lines or markdown separators.
    """
    return (
        f"[{score:.3f}] {file_path}\n"
        f"{content[:max_chars]}\n"
        f"--- <EOF {file_path}> ---\n"
        f"{RESULT_SEPARATOR}"
    )


def create_mcp_server(service: MemoryService) -> MCPServer:
    """Create an MCPServer exposing the memory service as tools."""
    server = MCPServer("dejavault")

    @server.tool(
        description=(
            "Search the memory repository for relevant memories. "
            "Use this whenever you need to recall information that may have been stored before, "
            "to find existing memories about a topic\n\n"
            "HOW TO USE:\n"
            "- query: the search text (required). Use natural language or keywords.\n"
            "- limit: max results to return, 1-100 (default 10).\n"
            "- search_type: 'hybrid' (default, best quality), 'keyword' (exact text match), "
            "or 'vector' (semantic similarity).\n\n"
            "RESPONSE FORMAT:\n"
            "Each result block ends with an explicit EOF marker:\n"
            "  [score] file_path\n"
            "  content (first 500 chars, may contain blank lines)\n"
            "  --- <EOF file_path> ---\n"
            "  ================ (40 '=' characters)\n"
            "The '--- <EOF ...> ---' line marks the end of one file's content.\n"
            "Higher score = more relevant. If nothing matches, returns exactly: 'No results found.'"
        )
    )
    def search_memory(query: str, limit: int = 10, search_type: str = "hybrid") -> str:
        """Search memories using keyword, vector, or hybrid search."""
        try:
            results = service.search(query, limit, search_type)
            if not results:
                return "No results found."
            return "\n".join(
                _format_result_block(r.score, r.file_path, r.content, 500) for r in results
            )
        except ValueError as e:
            return f"Error: {e}"

    @server.tool(
        description=(
            "Retrieve the full content of a single memory file. "
            "Use this when you know the exact file path and need the complete content "
            "(search_memory only returns a 500-char snippet).\n\n"
            "HOW TO USE:\n"
            "- file_path: path relative to the memory repo root, e.g. 'notes/ideas.md' "
            "(required). Do NOT include leading slashes or '..'.\n\n"
            "RESPONSE FORMAT:\n"
            "The raw markdown content of the file. "
            "If the file does not exist, returns: 'Memory file not found: <file_path>'"
        )
    )
    def get_memory(file_path: str) -> str:
        """Get the content of a memory file."""
        result = service.get(file_path)
        if result is None:
            return f"Memory file not found: {file_path}"
        return result["content"]

    @server.tool(
        description=(
            "Create a NEW memory file. Use this to store information you want to remember "
            "for future sessions (decisions, facts, notes, code patterns, etc.).\n\n"
            "HOW TO USE:\n"
            "- file_path: path for the new file, e.g. 'project_xy/issue_xy/solution.md', 'user/preferences.md' or 'systems/raspberry_pi/network_setup.md' etc. (required). "
            "Use subdirectories to organize. The file must NOT already exist.\n"
            "- content: markdown content (required). Use clear headings and structure.\n"
            "- commit_message: optional git commit message, used for memory versioning; a sensible default is generated.\n\n"
            "RESPONSE FORMAT:\n"
            "  Recorded <file_path> (commit <8-char-hash>)\n"
            "If the file already exists, returns: 'Error: Memory file already exists: <path> "
            "(use update to modify)' — in that case use update_memory instead."
        )
    )
    def record_memory(file_path: str, content: str, commit_message: str | None = None) -> str:
        """Record a new memory file."""
        try:
            result = service.record(file_path, content, commit_message)
            return f"Recorded {result['file_path']} (commit {result['commit_hash'][:8]})"
        except FileExistsError as e:
            return f"Error: {e}"
        except ValueError as e:
            return f"Error: {e}"

    @server.tool(
        description=(
            "Replace the ENTIRE content of an existing memory file. "
            "Use this to update a memory that already exists (e.g. after learning new information).\n\n"
            "HOW TO USE:\n"
            "- file_path: path to the existing file (required).\n"
            "- content: the complete new markdown content (required). This REPLACES everything.\n"
            "- commit_message: optional git commit message. Used for memory versioning\n\n"
            "RESPONSE FORMAT:\n"
            "  Updated <file_path> (commit <8-char-hash>)\n"
            "If the file does not exist, returns: 'Error: Memory file not found: <path>' — "
            "in that case use record_memory instead."
        )
    )
    def update_memory(file_path: str, content: str, commit_message: str | None = None) -> str:
        """Update an existing memory file."""
        try:
            result = service.update(file_path, content, commit_message)
            return f"Updated {result['file_path']} (commit {result['commit_hash'][:8]})"
        except FileNotFoundError as e:
            return f"Error: {e}"
        except ValueError as e:
            return f"Error: {e}"

    @server.tool(
        description=(
            "Apply a targeted text correction to a memory file WITHOUT rewriting the whole file. "
            "Use this when only a small part of a memory is wrong and you want to fix just that part.\n\n"
            "HOW TO USE:\n"
            "- file_path: path to the existing file (required).\n"
            "- old_content: the exact text to find and replace (required). Must be at least 3 "
            "characters and must match EXACTLY ONCE in the file. If it matches multiple times, "
            "the tool refuses to replace to avoid changing the wrong occurrence — in that case "
            "include more surrounding context in old_content to make it unique.\n"
            "- new_content: the replacement text (required).\n"
            "- commit_message: optional git commit message.\n\n"
            "RESPONSE FORMAT:\n"
            "  Corrected <file_path> (commit <8-char-hash>)\n"
            "Errors: 'Error: Memory file not found: <path>' or "
            "'Error: Old content not found in file' or "
            "'Error: Old content matches N times in file; refusing to replace...' or "
            "'Error: old_content must not be empty'"
        )
    )
    def correct_memory(file_path: str, old_content: str, new_content: str, commit_message: str | None = None) -> str:
        """Correct specific text within a memory file."""
        try:
            result = service.correct(file_path, old_content, new_content, commit_message)
            return f"Corrected {result['file_path']} (commit {result['commit_hash'][:8]})"
        except FileNotFoundError as e:
            return f"Error: {e}"
        except ValueError as e:
            return f"Error: {e}"

    @server.tool(
        description=(
            "Archive (permanently delete) a memory file. Use this to remove a memory that is "
            "no longer needed. The deletion is recorded in git history, so it can be recovered "
            "manually if needed.\n\n"
            "HOW TO USE:\n"
            "- file_path: path to the existing file to delete (required).\n"
            "- commit_message: optional git commit message.\n\n"
            "RESPONSE FORMAT:\n"
            "  Archived <file_path> (commit <8-char-hash>)\n"
            "If the file does not exist, returns: 'Error: Memory file not found: <path>'"
        )
    )
    def archive_memory(file_path: str, commit_message: str | None = None) -> str:
        """Archive (delete) a memory file."""
        try:
            result = service.archive(file_path, commit_message)
            return f"Archived {result['file_path']} (commit {result['commit_hash'][:8]})"
        except FileNotFoundError as e:
            return f"Error: {e}"
        except ValueError as e:
            return f"Error: {e}"

    @server.tool(
        description=(
            "Find memories that are semantically related to a given memory file. "
            "Use this to discover connections between memories, e.g. when exploring a topic "
            "or finding related context.\n\n"
            "HOW TO USE:\n"
            "- file_path: path to the memory file to find related memories for (required).\n"
            "- limit: max related results, 1-20 (default 5).\n\n"
            "RESPONSE FORMAT:\n"
            "Each result block ends with an explicit EOF marker:\n"
            "  [score] file_path\n"
            "  content (first 300 chars, may contain blank lines)\n"
            "  --- <EOF file_path> ---\n"
            "  ================ (40 '=' characters)\n"
            "The '--- <EOF ...> ---' line marks the end of one file's content.\n"
            "If none found or the file does not exist, returns: 'No related memories found.'"
        )
    )
    def list_related(file_path: str, limit: int = 5) -> str:
        """List memories related to a given file."""
        related = service.list_related(file_path, limit)
        if not related:
            return "No related memories found."
        return "\n".join(
            _format_result_block(r.score, r.file_path, r.content, 300) for r in related
        )

    @server.tool(
        description=(
            "Rebuild the vector search index from all markdown files in the repository. "
            "Use this if search results seem stale or missing, or after large manual changes "
            "to the memory files. This is a maintenance operation.\n\n"
            "HOW TO USE:\n"
            "- force: if true, delete and recreate the collection from scratch (default false). "
            "Use force=true only if the index is corrupted.\n\n"
            "RESPONSE FORMAT:\n"
            "  Indexed <N> files\n"
            "where N is the number of markdown files embedded."
        )
    )
    def rebuild_index(force: bool = False) -> str:
        """Rebuild the vector index from all markdown files."""
        import asyncio

        result = asyncio.run(service.rebuild_index(force))
        return f"Indexed {result['files_indexed']} files"

    return server
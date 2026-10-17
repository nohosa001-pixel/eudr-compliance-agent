"""
Discovery, SEO, Agent Manifests, and LLM Reference Endpoints.
"""
from pathlib import Path
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.core.config import settings

router = APIRouter(tags=["Discovery"])

# Resolving static directory
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}


@router.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    """Serves favicon."""
    svg_fav = STATIC_DIR / "favicon.svg"
    if svg_fav.exists():
        return FileResponse(str(svg_fav), media_type="image/svg+xml")
    return Response(status_code=204)


@router.get("/robots.txt", include_in_schema=False)
async def serve_robots():
    """Serves robots.txt for search engine crawlers."""
    robots_file = STATIC_DIR / "robots.txt"
    if robots_file.exists():
        return FileResponse(str(robots_file), media_type="text/plain")
    return Response(
        content="User-agent: *\nAllow: /\nSitemap: https://eudragent.com/sitemap.xml\n",
        media_type="text/plain"
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def serve_sitemap():
    """Serves sitemap.xml for search engines."""
    sitemap_file = STATIC_DIR / "sitemap.xml"
    if sitemap_file.exists():
        return FileResponse(str(sitemap_file), media_type="application/xml")
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://eudragent.com/</loc></url></urlset>',
        media_type="application/xml"
    )


@router.get("/llms.txt", include_in_schema=False)
async def serve_llms_txt():
    """Serves the standard llms.txt summary file for AI agents and LLM crawlers."""
    llms_file = STATIC_DIR / "llms.txt"
    if llms_file.exists():
        return FileResponse(str(llms_file), media_type="text/plain; charset=utf-8", headers=NO_CACHE_HEADERS)
    return PlainTextResponse("EUDR.agent: Visit https://eudragent.com/docs for API details.", headers=NO_CACHE_HEADERS)


@router.get("/llms-full.txt", include_in_schema=False)
async def serve_llms_full_txt():
    """Serves the comprehensive llms-full.txt reference for AI agents."""
    llms_full = STATIC_DIR / "llms-full.txt"
    if llms_full.exists():
        return FileResponse(str(llms_full), media_type="text/plain; charset=utf-8", headers=NO_CACHE_HEADERS)
    return PlainTextResponse("EUDR.agent Full Reference: Visit https://eudragent.com/openapi.json", headers=NO_CACHE_HEADERS)


@router.get("/agent.json", include_in_schema=False)
@router.get("/.well-known/agent.json", include_in_schema=False)
@router.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def serve_agent_manifest():
    """Serves the .well-known/agent.json plugin manifest for autonomous agents."""
    agent_file = STATIC_DIR / "agent.json"
    if agent_file.exists():
        return FileResponse(str(agent_file), media_type="application/json", headers=NO_CACHE_HEADERS)
    return JSONResponse({"name": "eudr_compliance_agent", "status": "active"}, headers=NO_CACHE_HEADERS)


@router.api_route("/.well-known/mcp/server-card.json", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
@router.api_route("/mcp/server-card.json", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
@router.api_route("/server-card.json", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
async def serve_mcp_server_card(request: Request):
    """Serves the standard MCP server-card.json metadata for Smithery.ai, Glama.ai, and MCP registries."""
    if request is not None and request.method in ("HEAD", "OPTIONS"):
        return Response(status_code=200, headers={"Allow": "GET, HEAD, OPTIONS", "Content-Type": "application/json"})
    
    # Lazy import to avoid loading heavy modules on startup
    from app.modules.agent_tools import AgentToolsRegistry
    
    tools = []
    for t in AgentToolsRegistry.list_tools():
        tools.append({
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["parameters"]
        })
    
    return JSONResponse({
        "serverInfo": {
            "name": "eudr-compliance-agent",
            "version": "1.4.0",
            "description": "Autonomous AI Agent compliance engine for European Union Deforestation Regulation (EU 2023/1115)."
        },
        "authentication": {"required": False},
        "tools": tools,
        "prompts": [
            {
                "name": "eudr_compliance_audit_prompt",
                "description": "Guides an autonomous agent through an end-to-end EUDR Art. 9 audit workflow: GIS plot check, deforestation check, VAT validation, and TRACES-NT DDS compilation."
            }
        ]
    }, headers=NO_CACHE_HEADERS)


@router.api_route("/glama.json", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
@router.api_route("/.well-known/glama.json", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
async def serve_glama_json(request: Request):
    """Serves the official glama.json metadata file for Glama.ai MCP indexer."""
    if request.method in ("HEAD", "OPTIONS"):
        return Response(status_code=200, headers={"Allow": "GET, HEAD, OPTIONS", "Content-Type": "application/json"})
    glama_static = STATIC_DIR / "glama.json"
    glama_root = Path(__file__).resolve().parent.parent.parent.parent / "glama.json"
    target_file = glama_static if glama_static.exists() else glama_root
    if target_file.exists():
        return FileResponse(str(target_file), media_type="application/json", headers=NO_CACHE_HEADERS)
    return JSONResponse({"name": "eudr-compliance-agent", "status": "active"}, headers=NO_CACHE_HEADERS)

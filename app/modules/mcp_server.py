"""
Model Context Protocol (MCP) Server Implementation.
Compliant with Model Context Protocol specification (v2024-11-05).
Supports JSON-RPC 2.0 over HTTP and stdio for Claude, Cursor, Antigravity, and AI Agents.
"""
from typing import Dict, Any, List, Optional
import json
import logging

from app.modules.agent_tools import AgentToolsRegistry
from app.core.exceptions import AgentSelfCorrectionError

logger = logging.getLogger("eudr.mcp_server")


class MCPServer:
    """Model Context Protocol (MCP) Server handler for EUDR Compliance."""

    SERVER_INFO = {
        "name": "eudr-compliance-mcp-server",
        "version": "1.2.0"
    }

    CAPABILITIES = {
        "tools": {
            "listChanged": False
        },
        "prompts": {
            "listChanged": False
        },
        "resources": {
            "subscribe": False,
            "listChanged": False
        }
    }

    PROMPTS = [
        {
            "name": "eudr_compliance_audit_prompt",
            "description": "Guides an autonomous agent through an end-to-end EUDR Art. 9 audit workflow: GIS plot check, deforestation check, VAT validation, and TRACES-NT DDS compilation.",
            "arguments": [
                {
                    "name": "operator_name",
                    "description": "Name of importing EU company",
                    "required": True
                },
                {
                    "name": "commodity",
                    "description": "Target commodity (e.g., cocoa, coffee, oil_palm)",
                    "required": True
                }
            ]
        }
    ]

    RESOURCES = [
        {
            "uri": "eudr://regulation/eu-2023-1115",
            "name": "EUDR Regulation 2023/1115 Baseline & Guidelines",
            "description": "Deforestation-free baseline criteria (cut-off date: 31 Dec 2020), Art. 9 plot polygon specifications, and TRACES-NT DDS mandate.",
            "mimeType": "text/markdown"
        },
        {
            "uri": "eudr://schema/traces-nt-dds-xml",
            "name": "TRACES-NT DDS XML Schema & Field Map",
            "description": "EU Commission Directorate-General for Health and Food Safety TRACES-NT XML submission schema format.",
            "mimeType": "application/xml"
        }
    ]

    @classmethod
    async def handle_jsonrpc_request(cls, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles incoming JSON-RPC 2.0 MCP requests.
        """
        req_id = request_data.get("id")
        method = request_data.get("method")
        params = request_data.get("params") or {}

        if not method:
            return cls._error_response(req_id, -32600, "Invalid Request: 'method' is required.")

        try:
            if method == "initialize":
                return cls._handle_initialize(req_id, params)
            elif method == "notifications/initialized":
                # Notifications don't require response, but return empty result if ID is provided
                return {"jsonrpc": "2.0", "id": req_id, "result": {}} if req_id is not None else {}
            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}
            elif method == "tools/list":
                return cls._handle_tools_list(req_id)
            elif method == "tools/call":
                return await cls._handle_tools_call(req_id, params)
            elif method == "prompts/list":
                return cls._handle_prompts_list(req_id)
            elif method == "prompts/get":
                return cls._handle_prompts_get(req_id, params)
            elif method == "resources/list":
                return cls._handle_resources_list(req_id)
            elif method == "resources/read":
                return cls._handle_resources_read(req_id, params)
            elif method == "resources/templates/list":
                return {"jsonrpc": "2.0", "id": req_id, "result": {"resourceTemplates": []}}
            else:
                return cls._error_response(req_id, -32601, f"Method not found: '{method}'.")
        except Exception as exc:
            logger.exception("Internal error in MCP handler")
            return cls._error_response(req_id, -32603, f"Internal JSON-RPC error: {str(exc)}")

    @classmethod
    def _handle_initialize(cls, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": cls.CAPABILITIES,
                "serverInfo": cls.SERVER_INFO,
                "instructions": (
                    "EUDR Compliance Agent MCP Server. "
                    "Use 'eudr_verify_plot' to validate plot coordinates, "
                    "'eudr_check_deforestation' to verify post-2020 canopy status, "
                    "'eudr_verify_vies_vat' to check EU tax numbers, and "
                    "'eudr_generate_dds' to generate TRACES-NT XML declarations."
                )
            }
        }

    @classmethod
    def _handle_tools_list(cls, req_id: Any) -> Dict[str, Any]:
        tools = []
        for t in AgentToolsRegistry.list_tools():
            # In MCP, the parameters schema is mapped to `inputSchema`
            tools.append({
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["parameters"]
            })
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": tools
            }
        }

    @classmethod
    async def _handle_tools_call(cls, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        try:
            result = await AgentToolsRegistry.execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ],
                    "isError": False
                }
            }
        except AgentSelfCorrectionError as sce:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(sce.to_dict(), ensure_ascii=False, indent=2)
                        }
                    ],
                    "isError": True
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "error": {
                                    "code": "EXECUTION_FAILURE",
                                    "message": str(e),
                                    "recoverable": False
                                }
                            })
                        }
                    ],
                    "isError": True
                }
            }

    @classmethod
    def _handle_prompts_list(cls, req_id: Any) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "prompts": cls.PROMPTS
            }
        }

    @classmethod
    def _handle_prompts_get(cls, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt_name = params.get("name")
        args = params.get("arguments") or {}
        op_name = args.get("operator_name", "[Operator Name]")
        commodity = args.get("commodity", "cocoa")

        if prompt_name == "eudr_compliance_audit_prompt":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": "Standardized EUDR audit instruction prompt for autonomous agents.",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    f"You are an autonomous EUDR compliance auditor for operator '{op_name}' importing '{commodity}'.\n"
                                    "Execute the following steps using MCP tools:\n"
                                    "1. Use 'eudr_verify_plot' to validate all plot geometries and ensure area rules (>= 4.0 ha requires polygons).\n"
                                    "2. Use 'eudr_check_deforestation' to verify no deforestation occurred after 31 December 2020.\n"
                                    "3. Use 'eudr_verify_vies_vat' to check operator and supplier VAT validity.\n"
                                    "4. Once verified, call 'eudr_generate_dds' to produce the TRACES-NT XML submission statement."
                                )
                            }
                        }
                    ]
                }
            }
        return cls._error_response(req_id, -32602, f"Prompt '{prompt_name}' not found.")

    @classmethod
    def _handle_resources_list(cls, req_id: Any) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "resources": cls.RESOURCES
            }
        }

    @classmethod
    def _handle_resources_read(cls, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = params.get("uri")
        if uri == "eudr://regulation/eu-2023-1115":
            content = (
                "# Regulation (EU) 2023/1115 (EUDR)\n\n"
                "## Key Directives:\n"
                "1. **Deforestation-free Baseline**: Products must not originate from land deforested after **31 December 2020**.\n"
                "2. **Legality of Production**: Production complies with local legal frameworks in country of harvest.\n"
                "3. **Geographic Precision**: High-accuracy coordinates required (< 4.0 ha: point allowed; >= 4.0 ha: complete polygon mandatory).\n"
                "4. **TRACES-NT DDS Submission**: Due Diligence Statement mandatory prior to entry into EU single market."
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "text/markdown",
                            "text": content
                        }
                    ]
                }
            }
        elif uri == "eudr://schema/traces-nt-dds-xml":
            content = (
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                "<TRACES-NT-DDS-Schema version=\"1.0\">\n"
                "  <RequiredElements>\n"
                "    <Operator vatNumber=\"string\" eoriNumber=\"string\"/>\n"
                "    <Commodity hsCode=\"string\" netMassKg=\"float\"/>\n"
                "    <ProductionPlots>\n"
                "      <Plot id=\"string\" areaHa=\"float\" geometry=\"GeoJSON/WKT\"/>\n"
                "    </ProductionPlots>\n"
                "    <CutoffCheck baseline=\"2020-12-31\" status=\"VERIFIED_ZERO_DEFORESTATION\"/>\n"
                "  </RequiredElements>\n"
                "</TRACES-NT-DDS-Schema>"
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/xml",
                            "text": content
                        }
                    ]
                }
            }
        return cls._error_response(req_id, -32602, f"Resource URI '{uri}' not found.")

    @classmethod
    def _error_response(cls, req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
        resp: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        if data is not None:
            resp["error"]["data"] = data
        return resp

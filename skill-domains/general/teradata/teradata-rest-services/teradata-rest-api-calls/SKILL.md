---
name: teradata-rest-api-calls
description: 'Execute HTTP requests (GET, POST, PUT, PATCH, DELETE) against any REST API endpoint directly from Teradata using custom_rest_call, custom_rest_get, and custom_rest_post tools. Supports JWT Bearer, HTTP Basic, and API-key authentication via saved connections or inline credentials. Ideal for integrating external services, webhooks, and third-party APIs into Teradata workflows.'
tags:
  - rest-api
  - http
  - integration
  - webhooks
  - teradata
---

## When to Use

Use this skill when you need to:
- Call Teradata REST APIs from within Teradata workflows
- Trigger webhooks or outbound notifications from Teradata queries
- Fetch data from external/internal HTTP endpoints and combine with Teradata data
- Execute CRUD operations against REST APIs (GET, POST, PUT, PATCH, DELETE)
- Authenticate using JWT Bearer tokens, HTTP Basic auth, or API keys
- Work with JSON payloads and structured API responses

Trigger keywords: 'REST API call', 'HTTP request', 'webhook', 'external API', 'POST request', 'GET request', 'API integration', 'third-party service'



## Core Concepts

### Tools Available

The Teradata REST pattern (`teradata-rest`) provides three tools:

1. **custom_rest_call** - Generic HTTP executor supporting all methods (GET, POST, PUT, PATCH, DELETE)
2. **custom_rest_get** - Specialized GET request executor
3. **custom_rest_post** - Specialized POST request executor with JSON payload support

Always ask the user to provide `system_name`, `protocol`, `port`, `path`, `method`, `payload`, and `query_string` parameters

### Authentication Methods

All tools support three authentication strategies:

1. **Saved Connection**: Reference a pre-configured connection from the `/connections` API using `system_connection_name`
2. **Inline Credentials**: Provide `system_name`, `protocol`, `port` directly in the tool call
3. **Bearer Token Fallback**: If no credentials are provided, the caller's Bearer token is used

### Response Format

- **JSON payloads**: Returned as structured rows/columns
- **Plain text responses**: Returned as a single 'response' column

## Procedures

### 1. Execute a Simple GET Request

Use `custom_rest_get` or `custom_rest_call` with `method: GET`:

```
teradata_tool_call(
  input={
    "name": "custom_rest_get",
    "parameters": {
      "system_name": "td-mcp-srv.teradata-mcp-server.svc.cluster.local",
      "protocol": "http",
      "port": "8001",
      "path": "/health",
      "query_string": "status=active&limit=10"
    },
    "long_running": false
  }
)
```

**Key Parameters**:
- `system_name` (string, optional): Hostname or IP of the target REST service
- `protocol` (string, optional): 'http' or 'https' (default: https)
- `port` (string, optional): TCP port (default: 443 for https, 80 for http)
- `path` (string, required): URL path with leading slash (e.g., '/api/v1/users')
- `query_string` (string, optional): URL query parameters without leading '?' (e.g., 'status=active&limit=10')

### 2. Execute a POST Request with JSON Payload

Use `custom_rest_post` or `custom_rest_call` with `method: POST`:

```
teradata_tool_call(
  input={
    "name": "custom_rest_post",
    "parameters": {
      "system_name": "hooks.slack.com",
      "protocol": "https",
      "path": "/services/YOUR/WEBHOOK/URL",
      "method": "POST",
      "payload": "{\"text\": \"Hello from Teradata!\", \"channel\": \"#general\"}"
    },
    "long_running": false
  }
)
```

**Key Parameters**:
- `payload` (string, optional): JSON body for POST, PUT, or PATCH requests. Must be a valid JSON object string. Ignored for GET and DELETE.

### 3. Use a Saved Connection

When you have a pre-configured connection in the `/connections` API:

```
teradata_tool_call(
  input={
    "name": "custom_rest_call",
    "parameters": {
      "system_connection_name": "my_api_connection",
      "path": "/api/v1/data",
      "method": "GET"
    },
    "long_running": false
  }
)
```

**Note**: When `system_connection_name` is provided, it overrides `system_name` and supplies stored credentials automatically.

### 4. Execute PUT or PATCH Requests

Use `custom_rest_call` with the appropriate method:

```
teradata_tool_call(
  input={
    "name": "custom_rest_call",
    "parameters": {
      "system_name": "api.example.com",
      "path": "/api/v1/users/123",
      "method": "PUT",
      "payload": "{\"name\": \"Updated Name\", \"status\": \"inactive\"}"
    },
    "long_running": false
  }
)
```

### 5. Execute DELETE Requests

```
teradata_tool_call(
  input={
    "name": "custom_rest_call",
    "parameters": {
      "system_name": "td-mcp-srv.teradata-mcp-server.svc.cluster.local",
      "path": "/api/v1/users/123",
      "method": "DELETE"
    },
    "long_running": false
  }
)
```

### 6. Discover Available REST Tools

Always search the `teradata-rest` pattern first:

```
teradata_search_tools(pattern="teradata-rest")
```

Then get the full schema for a specific tool:

```
teradata_get_tool_schema(tool_name="custom_rest_call")
```

## Common Errors

### 1. Missing Required Parameters

**Error**: "Missing required parameter: path"

**Solution**: Ensure `path` and `method` are always provided for `custom_rest_call`. The path must include a leading slash.

### 2. Invalid JSON Payload

**Error**: "Invalid JSON in payload parameter"

**Solution**: Ensure the `payload` parameter is a valid JSON string. Use double quotes for JSON keys and values, and escape inner quotes properly:

```
"payload": "{\"key\": \"value\", \"nested\": {\"inner\": \"data\"}}"
```

### 3. Authentication Failure

**Error**: "401 Unauthorized" or "403 Forbidden"

**Solution**: 
- Verify your `system_connection_name` is correct and has valid credentials
- If using inline credentials, ensure `system_name` matches the API host exactly
- Check that the Bearer token fallback has necessary permissions

### 4. Tool Not Found

**Error**: "Tool 'custom_rest_call' not found"

**Solution**: 
- First activate the Teradata search tools: `activate_tool(tool_name="teradata_search_tools", mcp_server="teradata-mcp-server")`
- Search for the tool: `teradata_search_tools(pattern="teradata-rest")`
- Execute via `teradata_tool_call` (never call the native tool directly)

### 5. Invalid Port Format

**Error**: "Port must be a string or integer"

**Solution**: Always pass port as a string: `"port": "443"` or `"port": "8080"`

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-rest-api-calls", path="references/FILENAME")` — do NOT call `list`.

- **Teradata REST Pattern**: Search with `teradata_search_tools(pattern="teradata-rest")` to discover all available tools
- **Tool Schema**: Use `teradata_get_tool_schema(tool_name="custom_rest_call")` for complete parameter documentation
- **Authentication**: Refer to the `/connections` API documentation for managing saved connections
- **HTTP Methods**: Supports GET, POST, PUT, PATCH, DELETE (case-sensitive)
- **Protocols**: Supports both HTTP and HTTPS

## Example Workflows

### Workflow 1: Fetch External Data and Join with Teradata Table

1. Use `custom_rest_get` to fetch JSON data from an external API
2. Always ask the user to provide `system_name`, `protocol`, `port`, `path`, `method`, `payload`, and `query_string` parameters
3. Response is returned as structured rows/columns
4. Use standard Teradata SQL to join the REST response with existing tables
5. Process and store the combined result

### Workflow 2: Trigger Webhook on Data Event

1. Query Teradata table for specific conditions
2. Use `custom_rest_post` to send webhook notifications when conditions are met
3. Pass query results as JSON payload to the webhook endpoint

### Workflow 3: CRUD Operations on External System

1. GET current state from external API
2. Process data in Teradata
3. PUT or PATCH updated data back to the external system
4. DELETE obsolete records when necessary

## Best Practices

1. **Always validate JSON payloads** before sending to avoid runtime errors
2. **Use saved connections** for production workflows to centralize credential management
3. **Test with GET requests first** before attempting POST/PUT/DELETE operations
4. **Handle response errors gracefully** and log API failures for debugging
5. **Use query_string parameter** for URL parameters instead of embedding them in the path
6. **Set appropriate timeout values** for long-running API calls
7. **Cache frequently accessed API responses** in Teradata tables to reduce external calls


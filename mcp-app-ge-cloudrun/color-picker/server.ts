import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import {
  McpServer,
  type CallToolResult,
  type ReadResourceResult,
} from "@modelcontextprotocol/server";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { normalizeHex, DEFAULT_COLOR } from "./src/color.ts";

// Works both from source (server.ts) and compiled (dist/server.js).
const SERVER_FILE = fileURLToPath(import.meta.url);
const DIST_DIR = SERVER_FILE.endsWith(".ts")
  ? path.join(path.dirname(SERVER_FILE), "dist")
  : path.dirname(SERVER_FILE);

/**
 * Creates a new MCP server instance exposing an interactive color-picker App.
 */
export function createServer(): McpServer {
  const server = new McpServer({
    name: "Color Picker MCP App",
    version: "1.0.0",
  });

  const resourceUri = "ui://pick-color/mcp-app.html";

  registerAppTool(server,
    "pick-color",
    {
      title: "Pick a Color",
      description:
        "Opens an interactive color picker. Optionally seed it with a starting color (hex).",
      inputSchema: z.object({
        initialColor: z
          .string()
          .optional()
          .describe("Starting color as a hex string, e.g. #3b82f6"),
      }),
      outputSchema: z.object({
        color: z.string().describe("Selected color as #rrggbb"),
      }),
      _meta: { ui: { resourceUri } },
    },
    async ({ initialColor }): Promise<CallToolResult> => {
      const color =
        (initialColor ? normalizeHex(initialColor) : null) ?? DEFAULT_COLOR;
      return {
        content: [{ type: "text", text: `Color picker ready at ${color}` }],
        structuredContent: { color },
      };
    },
  );

  registerAppResource(server,
    resourceUri,
    resourceUri,
    { mimeType: RESOURCE_MIME_TYPE },
    async (): Promise<ReadResourceResult> => {
      const html = await fs.readFile(
        path.join(DIST_DIR, "mcp-app.html"),
        "utf-8",
      );
      return {
        contents: [
          { uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html },
        ],
      };
    },
  );

  return server;
}

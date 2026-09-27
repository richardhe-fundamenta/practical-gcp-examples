/**
 * Entry point for running the MCP server.
 * HTTP (default):  npm run serve   ->  http://localhost:3001/mcp
 * stdio:           npm run serve:stdio
 *
 * The forwarded end-user OAuth token (Gemini Enterprise passes it on the
 * Authorization header) is extracted per request and handed to createServer so
 * BigQuery queries run as that user.
 */

import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { createMcpExpressApp } from "@modelcontextprotocol/express";
import type { McpServer } from "@modelcontextprotocol/server";
import { NodeStreamableHTTPServerTransport } from "@modelcontextprotocol/node";
import cors from "cors";
import type { Request, Response } from "express";
import { createServer } from "./server.js";

/** Pull the bearer token from the forwarded auth header, if present. */
function bearerToken(req: Request): string | undefined {
  const h =
    (req.headers["authorization"] as string | undefined) ??
    (req.headers["x-forwarded-authorization"] as string | undefined);
  if (h && h.toLowerCase().startsWith("bearer ")) return h.slice(7).trim();
  return undefined;
}

export async function startStreamableHTTPServer(
  createServer: (token?: string) => McpServer,
): Promise<void> {
  const port = parseInt(process.env.PORT ?? "3001", 10);

  const app = createMcpExpressApp({ host: "0.0.0.0" });
  app.use(cors());

  app.all("/mcp", async (req: Request, res: Response) => {
    const server = createServer(bearerToken(req));
    const transport = new NodeStreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
    });

    res.on("close", () => {
      transport.close().catch(() => {});
      server.close().catch(() => {});
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
    } catch (error) {
      console.error("MCP error:", error);
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: "2.0",
          error: { code: -32603, message: "Internal server error" },
          id: null,
        });
      }
    }
  });

  const httpServer = app.listen(port, (err) => {
    if (err) {
      console.error("Failed to start server:", err);
      process.exit(1);
    }
    console.log(`MCP server listening on http://localhost:${port}/mcp`);
  });

  const shutdown = () => {
    console.log("\nShutting down...");
    httpServer.close(() => process.exit(0));
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

export async function startStdioServer(
  createServer: (token?: string) => McpServer,
): Promise<void> {
  await createServer().connect(new StdioServerTransport());
}

async function main() {
  if (process.argv.includes("--stdio")) {
    await startStdioServer(createServer);
  } else {
    await startStreamableHTTPServer(createServer);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

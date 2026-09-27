/**
 * @file Color picker MCP App (vanilla JS + MCP Apps SDK).
 * Displays a native color picker; syncs a hex field and RGB readout; and can
 * report the chosen color back to the model.
 */
import {
  App,
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
  type McpUiHostContext,
} from "@modelcontextprotocol/ext-apps";
import type { CallToolResult } from "@modelcontextprotocol/client";
import { normalizeHex, hexToRgb, DEFAULT_COLOR } from "./color.ts";
import "./global.css";
import "./mcp-app.css";

const mainEl = document.querySelector(".main") as HTMLElement;
const swatchEl = document.getElementById("swatch") as HTMLElement;
const colorInput = document.getElementById("color-input") as HTMLInputElement;
const hexInput = document.getElementById("hex-input") as HTMLInputElement;
const rgbValue = document.getElementById("rgb-value") as HTMLElement;
const useColorBtn = document.getElementById("use-color-btn") as HTMLButtonElement;

/** Update every UI element to reflect a canonical `#rrggbb` color. */
function render(hex: string): void {
  colorInput.value = hex;
  hexInput.value = hex;
  swatchEl.style.backgroundColor = hex;
  const { r, g, b } = hexToRgb(hex);
  rgbValue.textContent = `${r}, ${g}, ${b}`;
}

let current = DEFAULT_COLOR;
function setColor(hex: string): void {
  current = hex;
  render(hex);
}

// Native picker always yields a valid #rrggbb.
colorInput.addEventListener("input", () => setColor(colorInput.value));

// Free-text hex: only commit when it parses; keep raw text otherwise so the
// user can keep typing.
hexInput.addEventListener("input", () => {
  const normalized = normalizeHex(hexInput.value);
  if (normalized) setColor(normalized);
});
hexInput.addEventListener("blur", () => render(current)); // snap back if invalid

function extractColor(result: CallToolResult): string {
  const { color } = (result.structuredContent as { color?: string }) ?? {};
  return (color && normalizeHex(color)) || DEFAULT_COLOR;
}

function handleHostContextChanged(ctx: McpUiHostContext) {
  if (ctx.theme) applyDocumentTheme(ctx.theme);
  if (ctx.styles?.variables) applyHostStyleVariables(ctx.styles.variables);
  if (ctx.styles?.css?.fonts) applyHostFonts(ctx.styles.css.fonts);
  if (ctx.safeAreaInsets) {
    mainEl.style.paddingTop = `${ctx.safeAreaInsets.top}px`;
    mainEl.style.paddingRight = `${ctx.safeAreaInsets.right}px`;
    mainEl.style.paddingBottom = `${ctx.safeAreaInsets.bottom}px`;
    mainEl.style.paddingLeft = `${ctx.safeAreaInsets.left}px`;
  }
}

const app = new App({ name: "Color Picker", version: "1.0.0" });

// Register ALL handlers BEFORE connecting.
app.onteardown = async () => ({});
app.ontoolresult = (result) => setColor(extractColor(result));
app.onerror = console.error;
app.onhostcontextchanged = handleHostContextChanged;

useColorBtn.addEventListener("click", async () => {
  try {
    const { isError } = await app.sendMessage({
      role: "user",
      content: [{ type: "text", text: `I picked the color ${current}.` }],
    });
    console.info("Color report", isError ? "rejected" : "accepted");
  } catch (e) {
    console.error(e);
  }
});

render(current);

app.connect().then(() => {
  const ctx = app.getHostContext();
  if (ctx) handleHostContextChanged(ctx);
});

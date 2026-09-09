/** Light cleanup for common resume paste artifacts (not aggressive LaTeX stripping). */

export function tidyPasteArtifacts(text: string): string {
  if (!text) return text;
  let cleaned = text.replace(/\r\n/g, "\n");
  cleaned = cleaned.replace(/\\%/g, "%");
  cleaned = cleaned.replace(/(\d+(?:\.\d+)?)\s*\/\s*%/g, "$1%");
  if (cleaned.includes("\\")) {
    cleaned = cleaned
      .replace(/\\item\b\s*/gi, "")
      .replace(/\\&/g, "&")
      .replace(/\\_/g, "_")
      .replace(/\\\$/g, "$")
      .replace(/\\#/g, "#")
      .replace(/\\\\/g, "\n");
  }
  return cleaned;
}

import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "mobile", "www");
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

for (const entry of ["js", "styles"]) await cp(path.join(root, entry), path.join(output, entry), { recursive: true });
for (const entry of ["styles.css"]) await cp(path.join(root, entry), path.join(output, entry));
await cp(path.join(root, "mobile", "mobile-connect.css"), path.join(output, "mobile-connect.css"));
await cp(path.join(root, "mobile", "mobile-entry.js"), path.join(output, "mobile-entry.js"));

const html = (await readFile(path.join(root, "index.html"), "utf8"))
  .replace('<script type="module" src="js/app.js"></script>', '<script type="module" src="mobile-entry.js"></script>')
  .replace('<link rel="stylesheet" href="styles.css" />', '<link rel="stylesheet" href="styles.css" />\n    <link rel="stylesheet" href="mobile-connect.css" />');
await writeFile(path.join(output, "index.html"), html);
console.log(`Prepared mobile web bundle at ${path.relative(root, output)} (application assets only).`);

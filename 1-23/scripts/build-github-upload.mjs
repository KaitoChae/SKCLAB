import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const sourceRoot = path.resolve(scriptDir, "..");
const outputDir = path.resolve(process.argv[2] || path.join(sourceRoot, "..", "Labskchaerun_GITHUB_ROOT_UPLOAD"));
const contentDir = path.join(outputDir, "1-23");

if (fs.existsSync(outputDir)) {
  throw new Error(`Output already exists: ${outputDir}`);
}

fs.mkdirSync(outputDir, { recursive: true });
fs.cpSync(sourceRoot, contentDir, {
  recursive: true,
  filter(source) {
    const relative = path.relative(sourceRoot, source);
    if (!relative) return true;
    const parts = relative.split(path.sep);
    return relative !== "index.html" && !parts.includes(".github") && !parts.includes("__pycache__");
  },
});

const sourceIndex = fs.readFileSync(path.join(sourceRoot, "index.html"), "utf8");
const rootIndex = sourceIndex
  .replace('<html lang="en">', '<html lang="en" data-asset-root="1-23/">')
  .replaceAll('content="assets/', 'content="1-23/assets/')
  .replaceAll('src="assets/', 'src="1-23/assets/')
  .replaceAll('href="assets/', 'href="1-23/assets/')
  .replaceAll('href="styles.css', 'href="1-23/styles.css')
  .replaceAll('src="data/', 'src="1-23/data/')
  .replaceAll('src="translations.js', 'src="1-23/translations.js')
  .replaceAll('src="script.js', 'src="1-23/script.js');

for (const tag of rootIndex.match(/<img\b[^>]*>/g) || []) {
  if (!/\ssrc="[^"]+"/.test(tag)) throw new Error(`Image tag has no valid src: ${tag}`);
}
if (/(?:src|href|content)="assets\//.test(rootIndex)) {
  throw new Error("An image or asset path still points outside the 1-23 folder");
}

fs.writeFileSync(path.join(outputDir, "index.html"), rootIndex);
fs.rmSync(path.join(contentDir, "index.html"), { force: true });

const optionalWorkflow = path.join(contentDir, "WORKFLOW_TO_PASTE_IN_GITHUB_ACTIONS.yml");
if (fs.existsSync(optionalWorkflow)) {
  const workflow = fs.readFileSync(optionalWorkflow, "utf8")
    .replaceAll("'scripts/**'", "'1-23/scripts/**'")
    .replaceAll("'requirements.txt'", "'1-23/requirements.txt'")
    .replaceAll("pip install -r requirements.txt", "pip install -r 1-23/requirements.txt")
    .replaceAll("python scripts/", "python 1-23/scripts/")
    .replaceAll(
      "git add data/publications.json data/publications.js data/research_projects.json data/research_projects.js assets/publications",
      "git add 1-23/data/publications.json 1-23/data/publications.js 1-23/data/research_projects.json 1-23/data/research_projects.js 1-23/assets/publications",
    );
  fs.writeFileSync(optionalWorkflow, workflow);
}

const localReferences = [...rootIndex.matchAll(/(?:src|href|content)="(1-23\/[^"?#]+)/g)].map((match) => match[1]);
const missingReferences = [...new Set(localReferences)].filter((reference) => !fs.existsSync(path.join(outputDir, reference)));
if (missingReferences.length) throw new Error(`Missing packaged files: ${missingReferences.join(", ")}`);

const rootEntries = fs.readdirSync(outputDir).sort();
if (rootEntries.join("|") !== "1-23|index.html") {
  throw new Error(`Unexpected root entries: ${rootEntries.join(", ")}`);
}
if (fs.existsSync(path.join(outputDir, ".github"))) throw new Error("The package must not contain a .github folder");

console.log(`GitHub upload package ready: ${outputDir}`);
console.log(`Validated ${new Set(localReferences).size} local root references.`);

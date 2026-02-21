// Minimal Node.js test runner (no external deps required).
const { greet, envInfo } = require("/workspace/src/hello.js");

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✓ ${message}`);
    passed++;
  } else {
    console.error(`  ✗ ${message}`);
    failed++;
  }
}

console.log("\n── Node.js tests ──────────────────────────────");

const greeting = greet("world");
assert(greeting.includes("world"), "greet() includes the name");
assert(greeting.includes("Node.js"), "greet() includes 'Node.js'");
assert(greeting.includes(process.version), "greet() includes runtime version");

const info = envInfo();
assert(typeof info.node === "string", "envInfo() has node field");
assert(typeof info.platform === "string", "envInfo() has platform field");
assert(typeof info.arch === "string", "envInfo() has arch field");

// Node version must be 20.x (as pinned in Dockerfile)
const majorVersion = parseInt(process.version.slice(1).split(".")[0], 10);
assert(majorVersion >= 20, `Node >= 20 (got ${process.version})`);

console.log(`\n  Results: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}

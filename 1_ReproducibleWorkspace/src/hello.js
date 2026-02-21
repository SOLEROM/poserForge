// Simple demo module — proves Node.js toolchain is functional.

function greet(name) {
  return `Hello from Node.js ${process.version}, ${name}!`;
}

function envInfo() {
  return {
    node: process.version,
    platform: process.platform,
    arch: process.arch,
  };
}

if (require.main === module) {
  console.log(greet("poserForge"));
  const info = envInfo();
  for (const [key, val] of Object.entries(info)) {
    console.log(`  ${key}: ${val}`);
  }
}

module.exports = { greet, envInfo };

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

const isWindows = process.platform === "win32";
const isWsl = Boolean(process.env.WSL_DISTRO_NAME || process.env.WSL_INTEROP);

function runCapture(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      shell: isWindows,
      stdio: ["ignore", "pipe", "ignore"]
    });
    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk.toString();
    });
    child.on("exit", (code) => {
      resolve(code === 0 ? output.trim() : "");
    });
    child.on("error", () => resolve(""));
  });
}

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      shell: isWindows,
      ...options
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${args.join(" ")} exited with code ${code}`));
    });
    child.on("error", reject);
  });
}

async function resolveDockerCommand() {
  const candidates = isWsl
    ? [
        "docker",
        "docker.exe",
        "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe",
        "/mnt/c/Program Files/Docker/Docker/resources/bin/com.docker.cli.exe"
      ]
    : ["docker", "docker.exe"];

  for (const candidate of candidates) {
    if (candidate.includes("/") && !existsSync(candidate)) {
      continue;
    }
    const version = await runCapture(candidate, ["--version"]);
    if (version) {
      return candidate;
    }
  }

  throw new Error(
    [
      "Docker CLI was not found, so WebIntel cannot start PostgreSQL, Redis, Kafka, Elasticsearch, or the backend containers.",
      "",
      isWsl
        ? "You are running from WSL. Install Docker Desktop for Windows, enable Settings > Resources > WSL integration for this distro, then reopen the terminal."
        : "Install Docker Desktop and make sure the docker command is available in PATH.",
      "",
      "After that, run: npm run dev",
      "For UI-only development without backend services, run: npm run dev:ui"
    ].join("\n")
  );
}

async function main() {
  const docker = await resolveDockerCommand();

  console.log("Starting WebIntel AI infrastructure and backend services...");
  await run(docker, ["compose", "up", "-d", "--build"]);

  console.log("Applying database migrations...");
  await run(docker, ["compose", "exec", "-T", "backend-api", "alembic", "upgrade", "head"]);

  console.log("Starting WebIntel AI operations console at http://localhost:5173");
  await run("node", ["node_modules/vite/bin/vite.js", "--host", "0.0.0.0"]);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});

/**
 * finance-mode.ts — Pi 侧接线层：把 knevo 的 skill 层挂到 Pi 原生的四个接缝上。
 *
 *   knevo 机制                      Pi 接缝
 *   ─────────────────────────────── ─────────────────────────────────────────────
 *   finance-mode 常驻 OS 层          before_agent_start → systemPromptOptions.sections["finance-mode"]
 *   专项 skill 渐进加载              pi --skill <dir>（Pi 自己列名字+描述，模型用 read 读 SKILL.md）
 *   spawn_sub_agent(preset, skill)   本文件注册的 spawn_sub_agent 工具：子 pi 进程、只读预设、恒挂 OS+一个专项
 *   交付前检查由模型执行             默认在 skill 正文里；FINANCE_PI_SECOND_LOOK=1 时 agent_before_settle 追加一次二看
 *   数据只走共享工具注册表           finance_call → bridge.py /tool（与 8792 同一份注册表与截止日）
 *
 * 只读守门：read 只允许读本进程已挂载的 SKILL.md（含真实路径校验），
 * 模型拿不到 bash / 直接读库的路。本文件不写记忆、不写文件（子任务输出只回到父进程上下文）。
 *
 * 环境变量（由 run_native.py 注入；手动起 pi 时自己 export）：
 *   FINANCE_PI_BRIDGE_URL   bridge 地址，默认 http://127.0.0.1:18886
 *   FINANCE_PI_MODEL        期望模型 id（provider 注册用），默认 glm-5.3-flash
 *   FINANCE_PI_CASE         case 标识，随请求头 X-Eval-Case 送到 bridge
 *   FINANCE_PI_SKILL_ROOT   含 <skill>/SKILL.md 的目录（仓内 skills/）
 *   FINANCE_PI_OS_SKILL     OS 层 skill 名，默认 finance-mode
 *   FINANCE_PI_APP_SKILLS   逗号分隔的专项名单，spawn_sub_agent 只接受这里面的
 *   FINANCE_PI_SUBAGENT_DEPTH  0=主线程；≥1=子任务（不再注册 spawn 工具）
 *   FINANCE_PI_SUBAGENTS    "1" 开启主线程派单；默认关，独立于 skill 层验收
 *   FINANCE_PI_MENU_FILE    已冻结的工具菜单与截止日，显式传给隔离子任务
 *   FINANCE_PI_SECOND_LOOK  "1" 开启 settle 前的一次自检续写（默认关，保持单变量）
 *   FINANCE_PI_THINKING / FINANCE_PI_BIN  子进程的 thinking 档位与 pi 可执行文件
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { spawn } from "node:child_process";
import { existsSync, readFileSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BRIDGE = (process.env.FINANCE_PI_BRIDGE_URL ?? "http://127.0.0.1:18886").replace(/\/$/, "");
const PROVIDER = "finance-eval";
const MODEL = process.env.FINANCE_PI_MODEL ?? "glm-5.3-flash";
const CASE = process.env.FINANCE_PI_CASE ?? "";
const SKILL_ROOT = process.env.FINANCE_PI_SKILL_ROOT ?? "";
const OS_SKILL = process.env.FINANCE_PI_OS_SKILL ?? "finance-mode";
const APP_SKILLS = (process.env.FINANCE_PI_APP_SKILLS ?? "")
	.split(",")
	.map((s) => s.trim())
	.filter(Boolean);
const DEPTH = Number(process.env.FINANCE_PI_SUBAGENT_DEPTH ?? "0") || 0;
const SECOND_LOOK = process.env.FINANCE_PI_SECOND_LOOK === "1";
const SUBAGENTS = process.env.FINANCE_PI_SUBAGENTS === "1";
const MENU_FILE = process.env.FINANCE_PI_MENU_FILE;
const THINKING = process.env.FINANCE_PI_THINKING ?? "low";
const PI_BIN = process.env.FINANCE_PI_BIN ?? "pi";
const SELF = fileURLToPath(import.meta.url);
const MAX_PARALLEL = 4; // knevo：并行 ≤3–4
const CHILD_OUTPUT_CAP = 50_000;
const CHILD_TIMEOUT_MS = 540_000;

function skillDir(name: string): string {
	return path.join(SKILL_ROOT, name);
}

function skillBody(name: string): string {
	const file = path.join(skillDir(name), "SKILL.md");
	const text = readFileSync(file, "utf8");
	const frontmatter = text.match(/^---\n[\s\S]*?\n---\n/);
	return (frontmatter ? text.slice(frontmatter[0].length) : text).trim();
}

function isMountedSkill(target: string, cwd: string): boolean {
	if (!SKILL_ROOT) return false;
	try {
		const root = realpathSync(SKILL_ROOT) + path.sep;
		const requested = path.resolve(cwd, target);
		const resolved = realpathSync(requested);
		return resolved.startsWith(root) && [OS_SKILL, ...APP_SKILLS].some((name) => {
			const file = path.resolve(skillDir(name), "SKILL.md");
			return requested === file && resolved === realpathSync(file);
		});
	} catch {
		return false;
	}
}

function childPrompt(task: string): string {
	if (!MENU_FILE) throw new Error("FINANCE_PI_MENU_FILE is required for isolated child research");
	const menu = JSON.parse(readFileSync(MENU_FILE, "utf8"));
	if (menu.case !== CASE || !menu.as_of || !Array.isArray(menu.authorized_tools)) {
		throw new Error("child tool menu does not match the configured research case");
	}
	return `Task: ${task}\n\nAuthorized tools and information cutoff:\n${JSON.stringify(menu)}`;
}

const RESEARCHER_PRESET = [
	"你是只读的研究子任务（finance-researcher 预设）。",
	"规则：只用 finance_call 取证；先用 read 读取已挂载的专项 SKILL.md，按它的检索顺序、骨架与交付前自检执行；",
	"不写文件、不写记忆、不派更多子任务；任务描述里没有的上下文不要臆测，缺就写缺。",
	"输出只交四段：结论（带条件）、依据（每条带来源与数据日期）、缺口与未取得、跟踪信号。不复述任务，不寒暄。",
].join("");

const SECOND_LOOK_PROMPT = [
	"交付前二看（只对表，不重写）：按 finance-mode 第 9 节逐条核对上面的回答——口径对账、时间顺序、去重、来源标注、缺口声明；",
	"再核一票否决清单。有缺就只补缺的那几句并重新给出完整回答；没有缺就原样再输出一遍完整回答。不要删掉已有依据的数字。",
].join("");

async function callBridge(toolName: string, args: Record<string, unknown>, signal?: AbortSignal): Promise<string> {
	const timeout = AbortSignal.timeout(150_000);
	const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
	const response = await fetch(`${BRIDGE}/tool`, {
		method: "POST",
		headers: { "Content-Type": "application/json", "X-Eval-Case": CASE },
		body: JSON.stringify({ tool: toolName, args }),
		signal: combined,
	});
	const text = await response.text();
	if (!response.ok) throw new Error(text);
	return text;
}

interface ChildTask {
	skill: string;
	title: string;
	task: string;
}

interface ChildResult {
	title: string;
	skill: string;
	exitCode: number | null;
	stopReason?: string;
	errorMessage?: string;
	text: string;
	truncated: boolean;
	stderrTail: string;
}

async function runChild(spec: ChildTask, signal?: AbortSignal): Promise<ChildResult> {
	signal?.throwIfAborted();
	const args = [
		"--print", "--mode", "json", "--no-session", "--offline", "--no-approve",
		"--no-extensions", "-e", SELF,
		"--no-skills", "--skill", skillDir(OS_SKILL), "--skill", skillDir(spec.skill),
		"--no-context-files", "--no-prompt-templates", "--no-themes",
		"--tools", "read,finance_call",
		"--provider", PROVIDER, "--model", MODEL, "--thinking", THINKING,
		"--append-system-prompt", RESEARCHER_PRESET,
		"--", childPrompt(spec.task),
	];
	return new Promise((resolve) => {
		const child = spawn(PI_BIN, args, {
			cwd: path.dirname(SELF),
			env: { ...process.env, FINANCE_PI_SUBAGENT_DEPTH: String(DEPTH + 1),
				FINANCE_PI_APP_SKILLS: spec.skill, FINANCE_PI_SECOND_LOOK: "0" },
			stdio: ["ignore", "pipe", "pipe"],
		});
		let buffer = "", stderr = "", text = "";
		let stopReason: string | undefined;
		let errorMessage: string | undefined;
		let termination: string | undefined;
		let killTimer: ReturnType<typeof setTimeout> | undefined;
		const terminate = (reason: string) => {
			termination = reason;
			child.kill("SIGTERM");
			killTimer ??= setTimeout(() => child.kill("SIGKILL"), 5000);
		};
		const timer = setTimeout(() => terminate("timeout"), CHILD_TIMEOUT_MS);
		const onAbort = () => terminate("aborted");
		signal?.addEventListener("abort", onAbort, { once: true });
		const consume = (line: string) => {
			if (!line.trim()) return;
			try {
				const event = JSON.parse(line);
				if (event?.type === "message_end" && event?.message?.role === "assistant") {
					const parts = Array.isArray(event.message.content) ? event.message.content : [];
					text = parts.filter((p: { type?: string }) => p?.type === "text")
						.map((p: { text?: string }) => p.text ?? "").join("\n");
					stopReason = event.message.stopReason;
					errorMessage = event.message.errorMessage;
				}
			} catch {
				errorMessage = "invalid child JSONL event";
				termination = "protocol_error";
			}
		};
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk: string) => {
			buffer += chunk;
			let newline: number;
			while ((newline = buffer.indexOf("\n")) !== -1) {
				consume(buffer.slice(0, newline));
				buffer = buffer.slice(newline + 1);
			}
		});
		child.stderr.setEncoding("utf8");
		child.stderr.on("data", (chunk: string) => { stderr = (stderr + chunk).slice(-2000); });
		child.on("error", (error) => { errorMessage = error.message; });
		child.on("close", (code) => {
			clearTimeout(timer);
			if (killTimer) clearTimeout(killTimer);
			signal?.removeEventListener("abort", onAbort);
			consume(buffer);
			const truncated = text.length > CHILD_OUTPUT_CAP;
			resolve({
				title: spec.title, skill: spec.skill, exitCode: code,
				stopReason: termination ?? stopReason, errorMessage,
				text: truncated ? text.slice(0, CHILD_OUTPUT_CAP) : text, truncated, stderrTail: stderr,
			});
		});
		if (signal?.aborted) onAbort();
	});
}

function childSucceeded(result: ChildResult): boolean {
	return result.exitCode === 0 && result.stopReason === "stop" && !!result.text.trim();
}

export default function financeMode(pi: ExtensionAPI) {
	let secondLookDone = false;
	let activeChildren = 0;
	pi.registerProvider(PROVIDER, {
		baseUrl: `${BRIDGE}/v1`,
		api: "openai-completions",
		apiKey: "evaluation-local",
		headers: { "X-Eval-Case": CASE },
		models: [{
			id: MODEL, name: "shared deployed endpoint via bridge", reasoning: true,
			input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
			contextWindow: 200000, maxTokens: 32768,
			compat: { supportsDeveloperRole: false, supportsStore: false, supportsReasoningEffort: false, maxTokensField: "max_tokens" },
		}],
	});

	// knevo 机制 A1/A7：OS 层整段常驻；专项只列名字，模型按需 read。
	pi.on("before_agent_start", (event) => {
		secondLookDone = false;
		if (SKILL_ROOT && existsSync(path.join(skillDir(OS_SKILL), "SKILL.md"))) {
			event.systemPromptOptions.sections["finance-mode"] = skillBody(OS_SKILL);
		}
		event.systemPromptOptions.promptGuidelines.push(
			"finance-mode 一节是常驻基础协议，每一轮都生效；skills 里列出的专项是应用层，命中时先 read 其 SKILL.md 再按骨架执行，未命中专项时仍按 finance-mode 完整执行。",
			"所有数据只能通过 finance_call 取得；read 只用于读取专项 skill 文件。",
		);
		if (SUBAGENTS && DEPTH === 0 && APP_SKILLS.length > 0) {
			event.systemPromptOptions.promptGuidelines.push(
				`需要派单时用 spawn_sub_agent，可派专项：${APP_SKILLS.join("、")}；并行不超过 ${MAX_PARALLEL} 个，子任务只读。`,
			);
		}
	});

	// 只读守门：read 仅限 skill 目录，数据不走文件系统。
	pi.on("tool_call", (event, ctx) => {
		if (event.toolName !== "read") return undefined;
		const input = event.input as { path?: unknown; file_path?: unknown };
		const target = String(input?.path ?? input?.file_path ?? "");
		if (!target || !isMountedSkill(target, ctx.cwd)) {
			return { block: true, reason: "read 只允许读取已挂载的 skill 文件；市场数据与资料一律通过 finance_call 获取" };
		}
		return undefined;
	});

	pi.registerTool({ name: "finance_call", label: "finance",
		description: "调用题面列出的已授权金融研究工具，args 必须遵循对应 schema。返回共享注册表的真实观察（带来源、日期与状态），与 8792 同一份工具与截止日。",
		parameters: Type.Object({
			tool: Type.String({ description: "授权清单里的工具名" }),
			args: Type.Object({}, { additionalProperties: true, description: "该工具的参数，按其 schema" }),
		}),
		async execute(_id, params, signal) {
			const text = await callBridge(params.tool, params.args as Record<string, unknown>, signal);
			return { content: [{ type: "text", text }], details: undefined };
		},
	});

	// knevo 机制 B5/B6/B7：派单只在主线程；子任务 = 独立 pi 进程 + 只读预设 + [OS, 一个专项]。
	if (SUBAGENTS && DEPTH === 0 && APP_SKILLS.length > 0) {
		pi.registerTool({ name: "spawn_sub_agent", label: "sub-agent",
			description: `派出只读研究子任务（finance-researcher 预设，独立上下文，恒挂 finance-mode + 一个专项）。单个：{skill,title,task}；并行：{tasks:[…]}（最多 ${MAX_PARALLEL} 个，彼此不能有信息流依赖）。task 写三段：范围点列、用户记忆线索、输出格式约定；子任务读不到本对话。返回每个子任务的最终文本，父线程负责汇总、对齐口径与保留缺口。短问题不要派单。`,
			parameters: Type.Object({
				skill: Type.Optional(Type.String({ description: `专项名，之一：${APP_SKILLS.join(" | ")}` })),
				title: Type.Optional(Type.String({ description: "子任务标题，≤20 字" })),
				task: Type.Optional(Type.String({ description: "自足的任务描述（范围 / 记忆线索 / 输出约定）" })),
				tasks: Type.Optional(Type.Array(Type.Object({
					skill: Type.String(), title: Type.String(), task: Type.String(),
				}), { description: "并行子任务列表" })),
			}),
			async execute(_id, params, signal) {
				const specs: ChildTask[] = params.tasks && params.tasks.length > 0
					? params.tasks
					: [{ skill: params.skill ?? "", title: params.title ?? "sub-task", task: params.task ?? "" }];
				if (specs.length > MAX_PARALLEL) throw new Error(`parallel sub-agents capped at ${MAX_PARALLEL}`);
				for (const spec of specs) {
					if (!APP_SKILLS.includes(spec.skill)) throw new Error(`unknown app skill: ${spec.skill}; allowed: ${APP_SKILLS.join(", ")}`);
					if (!spec.task.trim()) throw new Error("task must be a self-contained description");
				}
				if (activeChildren + specs.length > MAX_PARALLEL) throw new Error("parallel sub-agent budget exhausted");
				activeChildren += specs.length;
				try {
					const results = await Promise.all(specs.map((spec) => runChild(spec, signal)));
					const text = results.map((r) => [
						`### ${r.title}（${r.skill}${r.truncated ? "，已截断" : ""}）`,
						childSucceeded(r) ? r.text : `FAILED: ${r.stopReason ?? "process_error"}; ${r.errorMessage ?? r.stderrTail}`,
					].join("\n")).join("\n\n");
					if (results.every((r) => !childSucceeded(r))) throw new Error(`all sub-agents failed: ${text.slice(0, 2000)}`);
					return { content: [{ type: "text", text }], details: { results: results.map(({ stderrTail: _s, ...rest }) => rest) } };
				} finally {
					activeChildren -= specs.length;
				}
			},
		});
	}

	// knevo 机制 A5 的可选形状：交付前再看一眼，不拒稿、不重写、只补缺。默认关。
	pi.on("agent_before_settle", (event) => {
		if (!SECOND_LOOK || secondLookDone || event.outcome !== "completed" || event.continue) return undefined;
		secondLookDone = true;
		return {
			entries: [{ type: "custom_message", customType: "finance-second-look", content: SECOND_LOOK_PROMPT, display: true }],
			continue: true,
		};
	});
}

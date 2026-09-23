import fs from 'node:fs';
import path from 'node:path';
import { createBashTool } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/index.js';

export default function (pi) {
  const root = path.dirname(new URL(import.meta.url).pathname);
  const tree = path.join(root, 'candidate');
  const work = fs.realpathSync(process.env.REVIEW_WORK);
  const quote = value => "'" + value.replaceAll("'", "'\\''") + "'";
  const tool = createBashTool(tree, {
    exposeSessionEnvironment: false,
    spawnHook: ({ command, cwd, env }) => ({
      command: '/usr/bin/sandbox-exec -f ' + quote(path.join(root, 'tools.sb')) + ' /bin/bash --noprofile --norc -c ' + quote(command),
      cwd,
      env,
    }),
  });
  pi.registerTool({ ...tool, execute: (id, params, signal, update) => tool.execute(id, params, signal, update) });
  pi.on('tool_call', event => {
    if (['read', 'write'].includes(event.toolName)) {
      const requested = path.resolve(tree, event.input.path);
      const parent = event.toolName === 'write' ? path.dirname(requested) : requested;
      let canonical;
      try { canonical = fs.realpathSync(parent); } catch { canonical = parent; }
      if (event.toolName === 'write' && !canonical.startsWith(work + path.sep) && canonical !== work)
        return { block: true, reason: 'Only reviewer work output is writable.' };
      if (event.toolName === 'read') {
        const within = base => canonical === base || canonical.startsWith(base + path.sep);
        const excluded = ['docs/handoffs', 'docs/verification', 'intelligence/users', 'db', '.agent-memory', '.git', '.env'].some(p => within(path.join(tree, p)));
        if (!(within(work) || (within(tree) && !excluded) || canonical === path.join(root, 'source.diff')))
          return { block: true, reason: 'Read only fixed candidate source, source.diff, or reviewer work; no author reports, credentials, or production data.' };
      }
    }
  });
}

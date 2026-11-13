(() => {
  const repo = 'https://github.com/AlexBloom/font-reviver';
  const pip = `python -m pip install 'git+${repo}.git@main'`;
  const systems = {
    mac: {
      label: 'TERMINAL · macOS',
      setup: ['brew install python git fontforge', 'python3 -m venv ~/.venvs/font-reviver', 'source ~/.venvs/font-reviver/bin/activate', pip],
      venv: ['python3 -m venv .venv', 'source .venv/bin/activate'],
      note: 'You’ll need Git and Python 3.10+ (3.11+ recommended). FontForge handles legacy outline conversion. Homebrew installs the macOS dependencies above.',
      path: '"$HOME/Desktop/Old Fonts"'
    },
    linux: {
      label: 'TERMINAL · DEBIAN / UBUNTU',
      setup: ['sudo apt-get install git python3-venv fontforge python3-fontforge', 'python3 -m venv ~/.venvs/font-reviver', '. ~/.venvs/font-reviver/bin/activate', pip],
      venv: ['python3 -m venv .venv', '. .venv/bin/activate'],
      note: 'These dependency commands are for Debian / Ubuntu. On other distributions, install Python 3.10+, Git, and a FontForge build with Python scripting using your package manager.',
      path: '"$HOME/Desktop/Old Fonts"'
    },
    windows: {
      label: 'POWERSHELL · WINDOWS',
      setup: ['py -m venv "$HOME\\.venvs\\font-reviver"', '& "$HOME\\.venvs\\font-reviver\\Scripts\\Activate.ps1"', pip, '$env:FONTFORGE = "C:\\Program Files (x86)\\FontForgeBuilds\\bin\\fontforge.exe"'],
      venv: ['py -m venv .venv', '& .\\.venv\\Scripts\\Activate.ps1'],
      note: 'Install Python 3.10+, Git, and FontForge with Python scripting first. Set FONTFORGE to the executable actually installed on your computer; its path varies.',
      path: '"$HOME\\Desktop\\Old Fonts"'
    }
  };
  const methods = {
    app: {title: 'Your collection, with a view.', description: 'Install once, open the local app, and paste the path to your font folder. Everything runs on your computer.', next: 'When the app opens, point it at your desktop font folder. Leave the destination blank to create a separate revived collection.'},
    cli: {title: 'Bring a whole folder back.', description: 'Inspect first, then recover usable fonts. The CLI emits JSON reports and saves a searchable gallery beside your collection.', next: 'Open Gallery.html in the output folder. report.json and results.csv list successful files, skipped placeholders, and items needing attention.'},
    agent: {title: 'Your agent. The same revival.', description: 'Install the engine, clone the skill, then add it to your agent’s skill directory. The workflow works through standard CLI, Python, or local HTTP interfaces.', next: 'Ask your agent: “Use Font Reviver to inspect my font folder, revive recoverable files into a separate folder, and show the gallery and exceptions.”'},
    fork: {title: 'Make it your kind of tool.', description: 'Fork the repository on GitHub, then clone your fork. The app, CLI, API, and skill are all in one open-source project.', next: 'Replace YOUR-USERNAME with your GitHub username. Install Python, Git, and FontForge first. The README includes the platform-specific dependencies.'}
  };
  let method = 'app', os = 'mac';
  const tabs = [...document.querySelectorAll('[data-method]')];
  const osButtons = [...document.querySelectorAll('[data-os]')];
  const code = document.getElementById('install-command');
  const status = document.getElementById('copy-status');
  const copyButton = document.getElementById('copy-command');
  let resetTimer;
  function commands() {
    const system = systems[os];
    if (method === 'app') return [...system.setup, 'font-reviver ui'];
    if (method === 'cli') return [...system.setup, '', 'font-reviver doctor', `font-reviver scan ${system.path}`, `font-reviver convert ${system.path}`];
    if (method === 'agent') {
      const copy = os === 'windows'
        ? ['New-Item -ItemType Directory -Force "$HOME\\.codex\\skills"', 'Copy-Item -Recurse font-reviver/skills/font-reviver "$HOME\\.codex\\skills\\font-reviver"']
        : ['mkdir -p ~/.codex/skills', 'cp -R font-reviver/skills/font-reviver ~/.codex/skills/'];
      return [...system.setup, '', `git clone ${repo}.git`, ...copy];
    }
    return ['git clone https://github.com/YOUR-USERNAME/font-reviver.git', 'cd font-reviver', ...system.venv, "python -m pip install -e '.[dev]'", 'python -m pytest', 'font-reviver ui'];
  }
  function render() {
    tabs.forEach(tab => {const active = tab.dataset.method === method; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;});
    osButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.os === os)));
    document.getElementById('install-panel').setAttribute('aria-labelledby', 'tab-' + method);
    document.getElementById('method-title').textContent = methods[method].title;
    document.getElementById('method-description').textContent = methods[method].description;
    document.getElementById('next-step').textContent = methods[method].next;
    document.getElementById('terminal-label').textContent = systems[os].label;
    document.getElementById('install-note').textContent = systems[os].note + (method === 'agent' ? ' The copy command installs the skill for Codex. For Claude Code, use ~/.claude/skills instead; other agents can read SKILL.md directly. Keep the app environment active, or use the included portable skill runner.' : '');
    code.textContent = commands().join('\n');
    clearTimeout(resetTimer);
    copyButton.textContent = 'Copy commands ⧉';
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => {method = tab.dataset.method; render();});
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index+1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index+tabs.length-1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length-1;
      if (next !== undefined) {event.preventDefault(); method = tabs[next].dataset.method; render(); tabs[next].focus();}
    });
  });
  osButtons.forEach(button => button.addEventListener('click', () => {os = button.dataset.os; render();}));
  copyButton.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(code.textContent);
      copyButton.textContent = 'Copied ✓';
      status.textContent = 'Installation commands copied to clipboard.';
      resetTimer = setTimeout(() => copyButton.textContent = 'Copy commands ⧉', 2500);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange(); range.selectNodeContents(code); selection.removeAllRanges(); selection.addRange(range);
      status.textContent = 'Commands selected. Use your usual copy shortcut.';
      copyButton.textContent = 'Selected — press copy';
    }
  });
  render();
})();

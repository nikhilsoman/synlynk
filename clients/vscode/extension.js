const vscode = require('vscode');
const { exec } = require('child_process');

function runInTerminal(command, title = 'Synlynk') {
    let terminal = vscode.window.terminals.find(t => t.name === title);
    if (!terminal) {
        terminal = vscode.window.createTerminal(title);
    }
    terminal.show();
    terminal.sendText(command);
}

function activate(context) {
    // 1. synlynk.dispatch
    const dispatchCmd = vscode.commands.registerCommand('synlynk.dispatch', async () => {
        const task = await vscode.window.showInputBox({
            prompt: 'Enter task description for agent execution',
            placeHolder: 'e.g. Implement unit test for authentication service',
        });
        if (!task) return;

        const harness = await vscode.window.showQuickPick(
            [
                { label: 'Auto (Recommended)', description: 'Adaptive EV capability routing' },
                { label: 'Codex', description: 'OpenAI Codex' },
                { label: 'Claude', description: 'Anthropic Claude' },
                { label: 'Agy', description: 'Google Gemini (AntiGravity)' },
                { label: 'Grok', description: 'xAI Grok' },
            ],
            { placeHolder: 'Select execution harness' }
        );
        if (!harness) return;

        let cmd = `synlynk dispatch --task "${task.replace(/"/g, '\\"')}"`;
        if (harness.label !== 'Auto (Recommended)') {
            cmd += ` ${harness.label.toLowerCase()} --force-harness`;
        }
        runInTerminal(cmd, 'Synlynk Dispatch');
    });

    // 2. synlynk.jobs
    const jobsCmd = vscode.commands.registerCommand('synlynk.jobs', () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        const cwd = workspaceFolders ? workspaceFolders[0].uri.fsPath : process.cwd();

        exec('synlynk jobs --json', { cwd }, (err, stdout) => {
            if (err) {
                vscode.window.showErrorMessage(`Failed to fetch jobs: ${err.message}`);
                return;
            }
            try {
                const jobs = JSON.parse(stdout);
                if (!jobs || jobs.length === 0) {
                    vscode.window.showInformationMessage('No active or recent Synlynk jobs.');
                    return;
                }
                const items = jobs.slice(0, 15).map(j => ({
                    label: `${j.id} [${j.status || 'unknown'}]`,
                    description: `${j.agent || ''} | ${j.story_id || ''}`,
                    detail: `Tokens: ${j.tokens || 0} | Cost: $${j.cost_usd || 0} | Exit: ${j.exit_code !== undefined ? j.exit_code : 'running'}`,
                    jobId: j.id,
                }));
                vscode.window.showQuickPick(items, { placeHolder: 'Select a job to view logs' }).then(selected => {
                    if (selected) {
                        runInTerminal(`synlynk logs --job ${selected.jobId}`, 'Synlynk Logs');
                    }
                });
            } catch (parseErr) {
                runInTerminal('synlynk jobs', 'Synlynk Jobs');
            }
        });
    });

    // 3. synlynk.status
    const statusCmd = vscode.commands.registerCommand('synlynk.status', () => {
        runInTerminal('synlynk status', 'Synlynk Status');
    });

    // 4. synlynk.logs
    const logsCmd = vscode.commands.registerCommand('synlynk.logs', async () => {
        const jobId = await vscode.window.showInputBox({
            prompt: 'Enter Job ID to view logs (leave empty for latest job)',
            placeHolder: 'e.g. job-3bd46aec',
        });
        const cmd = jobId ? `synlynk logs --job ${jobId.trim()}` : 'synlynk logs';
        runInTerminal(cmd, 'Synlynk Logs');
    });

    // 5. synlynk.doctor
    const doctorCmd = vscode.commands.registerCommand('synlynk.doctor', () => {
        runInTerminal('synlynk doctor', 'Synlynk Doctor');
    });

    context.subscriptions.push(dispatchCmd, jobsCmd, statusCmd, logsCmd, doctorCmd);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate,
};

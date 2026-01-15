class MCPAgentUI {
    constructor() {
        this.isStreaming = false;
        this.currentStream = null;
        this.abortController = null;
        this.currentSessionId = localStorage.getItem('current_session_id');
        this.messageCount = 0;

        // Get DOM elements
        this.elements = {
            chatMessages: document.getElementById('chat-messages'),
            messageInput: document.getElementById('message-input'),
            sendButton: document.getElementById('send-button'),
            stopButton: document.getElementById('stop-button'),
            toolShortcuts: document.getElementById('tool-shortcuts'),
            statusIndicator: document.getElementById('status-indicator'),
            toolViewer: document.getElementById('tool-viewer'),
            toolLogs: document.getElementById('tool-logs'),
            toolCount: document.getElementById('tool-count-total'),
            toolSuccess: document.getElementById('tool-success-rate'),
            newChatButton: document.getElementById('new-chat-button'),
            modelSelect: document.getElementById('model-select'),
            temperatureSlider: document.getElementById('temperature-slider'),
            temperatureValue: document.getElementById('temperature-value')
        };

        // Initialize
        this.initEventListeners();
        this.loadTools();
        this.loadStatus();
        if (this.currentSessionId) {
            this.loadSession(this.currentSessionId);
        }
        this.updateStatus('idle');
        this.setupTheme();
        this.setupResizers();
    }

    setupTheme() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        if (savedTheme === 'dark') {
            document.documentElement.classList.add('dark');
        }
    }

    initEventListeners() {
        // Send message on Enter (without Shift)
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                this.sendMessage();
            }
            // Ctrl+Enter or Cmd+Enter also sends
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Send button
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());

        // Stop button
        this.elements.stopButton.addEventListener('click', () => this.stopGeneration());

        // New chat button
        if (this.elements.newChatButton) {
            this.elements.newChatButton.addEventListener('click', () => {
                localStorage.removeItem('current_session_id');
                window.location.reload();
            });
        }

        // Auto-resize textarea
        this.elements.messageInput.addEventListener('input', () => {
            this.elements.messageInput.style.height = 'auto';
            const newHeight = Math.min(this.elements.messageInput.scrollHeight, 200);
            this.elements.messageInput.style.height = newHeight + 'px';
            this.elements.sendButton.disabled = !this.elements.messageInput.value.trim();
        });

        // Model selection
        if (this.elements.modelSelect) {
            this.elements.modelSelect.addEventListener('change', () => {
                this.updateConfig({ model: this.elements.modelSelect.value });
            });
        }

        // Temperature slider
        if (this.elements.temperatureSlider) {
            this.elements.temperatureSlider.addEventListener('input', () => {
                const val = this.elements.temperatureSlider.value;
                this.elements.temperatureValue.textContent = val;
            });
            this.elements.temperatureSlider.addEventListener('change', () => {
                this.updateConfig({ temperature: this.elements.temperatureSlider.value });
            });
        }
    }

    async updateConfig(params) {
        try {
            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });
        } catch (error) {
            console.error('Failed to update config:', error);
        }
    }

    setupResizers() {
        const resizerLeft = document.getElementById('resizer-left');
        const resizerRight = document.getElementById('resizer-right');
        const resizerInput = document.getElementById('resizer-input');
        const resizerContextV = document.getElementById('resizer-context-v');
        const resizerToolV = document.getElementById('resizer-tool-v');

        const contextPanel = document.getElementById('context-panel');
        const toolViewer = document.getElementById('tool-viewer');
        const inputArea = document.getElementById('input-area');

        const contextPanelTop = document.getElementById('context-panel-top');
        const toolViewerTop = document.getElementById('tool-viewer-top');

        // Horizontal Resizing (Left Panel)
        if (resizerLeft && contextPanel) {
            this.handleResizer(resizerLeft, contextPanel, 'width', 'clientX', true);
        }

        // Horizontal Resizing (Right Panel)
        if (resizerRight && toolViewer) {
            this.handleResizer(resizerRight, toolViewer, 'width', 'clientX', false);
        }

        // Vertical Resizing (Input Area)
        if (resizerInput && inputArea) {
            this.handleResizer(resizerInput, inputArea, 'height', 'clientY', false);
        }

        // Vertical Resizing (Context Panel Sections)
        if (resizerContextV && contextPanelTop) {
            this.handleResizer(resizerContextV, contextPanelTop, 'height', 'clientY', true);
        }

        // Vertical Resizing (Tool Viewer Sections)
        if (resizerToolV && toolViewerTop) {
            this.handleResizer(resizerToolV, toolViewerTop, 'height', 'clientY', true);
        }
    }

    handleResizer(resizer, target, property, coord, isPositive) {
        let startCoord, startSize;

        const onMouseMove = (e) => {
            const delta = e[coord] - startCoord;
            const newSize = isPositive ? (startSize + delta) : (startSize - delta);

            if (property === 'width') {
                if (newSize > 150 && newSize < 600) target.style.width = newSize + 'px';
            } else {
                if (newSize > 80 && newSize < 600) target.style.height = newSize + 'px';
            }
        };

        const onMouseUp = () => {
            resizer.classList.remove('active');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };

        resizer.addEventListener('mousedown', (e) => {
            startCoord = e[coord];
            startSize = parseInt(document.defaultView.getComputedStyle(target)[property], 10);
            resizer.classList.add('active');
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
            e.preventDefault();
        });
    }

    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || this.isStreaming) return;

        // Clear input and disable button
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';
        this.elements.sendButton.disabled = true;

        // Add user message to UI
        this.addMessage('user', message);

        // Start streaming response
        await this.streamResponse(message);
    }

    async streamResponse(message) {
        this.isStreaming = true;
        this.updateStatus('thinking');
        this.elements.stopButton.classList.remove('hidden');

        // Create assistant message container
        const messageId = this.addMessage('assistant', '');
        let fullContent = '';

        this.abortController = new AbortController();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                signal: this.abortController.signal,
                body: JSON.stringify({
                    message: message,
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) {
                if (response.status === 503) {
                    throw new Error('Agent is still connecting to MCP servers. Please wait a few seconds and try again.');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));

                            // Accumulate content and handle events
                            if (data.type === 'content') {
                                fullContent += data.content;
                                this.updateMessageContent(messageId, fullContent);
                            } else {
                                this.handleStreamEvent(data, messageId);
                            }

                            if (data.type === 'complete' && data.session_id) {
                                this.currentSessionId = data.session_id;
                                localStorage.setItem('current_session_id', data.session_id);
                            }
                        } catch (e) {
                            console.warn('Error parsing SSE data:', e, line);
                        }
                    }
                }
            }

        } catch (error) {
            console.error('Streaming error:', error);
            // Remove the empty assistant message if nothing was received
            if (!fullContent) {
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) messageElement.remove();
            }
            if (error.name !== 'AbortError') {
                this.addSystemMessage(`${error.message}`, 'error');
            }
        } finally {
            this.isStreaming = false;
            this.abortController = null;
            this.updateStatus('idle');
            this.elements.stopButton.classList.add('hidden');

            // Add copy button to final message
            const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageElement && fullContent) {
                this.addCopyButton(messageElement, fullContent);
            }

            // Re-enable send button
            this.elements.sendButton.disabled = false;
        }
    }

    handleStreamEvent(data, messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;

        const contentElement = messageElement.querySelector('.prose');

        switch (data.type) {
            case 'tool_start':
                this.addToolCall(data);
                break;

            case 'tool_result':
                this.updateToolResult(data);
                break;

            case 'error':
                this.addSystemMessage(data.message, 'error');
                break;

            case 'complete':
                console.log('Stream complete');
                break;
        }
    }

    stopGeneration() {
        if (this.abortController) {
            this.abortController.abort();
        }
        this.isStreaming = false;
        this.updateStatus('idle');
        this.elements.stopButton.classList.add('hidden');
        this.elements.sendButton.disabled = false;
    }

    addMessage(role, content) {
        const messageId = `msg_${Date.now()}_${this.messageCount++}`;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message group mb-6';
        messageDiv.dataset.messageId = messageId;

        if (role === 'user') {
            messageDiv.innerHTML = `
                <div class="flex justify-end">
                    <div class="max-w-[80%]">
                        <div class="bg-blue-600 text-white rounded-2xl rounded-br-none px-4 py-3">
                            <div class="prose prose-invert max-w-none">${marked.parse(content)}</div>
                        </div>
                        <div class="text-xs text-gray-500 dark:text-gray-400 mt-1 text-right">
                            ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                    </div>
                </div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div class="flex gap-3">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                            <svg class="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="font-medium text-sm">MCP Agent</span>
                            <span class="text-xs text-gray-500 dark:text-gray-400">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <div class="prose dark:prose-invert max-w-none bg-white dark:bg-gray-800 rounded-2xl rounded-tl-none px-4 py-3">
                            ${this.escapeHtml(content)}
                        </div>
                        <div class="mt-2 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button class="copy-btn text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800">
                                Copy
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        this.elements.chatMessages.appendChild(messageDiv);
        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });

        return messageId;
    }

    updateMessageContent(messageId, content) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;

        const contentElement = messageElement.querySelector('.prose');
        if (contentElement) {
            // Use marked to render markdown
            contentElement.innerHTML = marked.parse(content);
            this.highlightCodeBlocks(contentElement);

            // Auto-scroll if near bottom
            const container = this.elements.chatMessages;
            const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
            if (isNearBottom) {
                messageElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        }
    }

    addSystemMessage(content, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'my-4 text-center';

        let bgColor = 'bg-gray-100 dark:bg-gray-800';
        let textColor = 'text-gray-600 dark:text-gray-400';

        if (type === 'error') {
            bgColor = 'bg-red-100 dark:bg-red-900/30';
            textColor = 'text-red-700 dark:text-red-400';
        } else if (type === 'success') {
            bgColor = 'bg-green-100 dark:bg-green-900/30';
            textColor = 'text-green-700 dark:text-green-400';
        }

        messageDiv.innerHTML = `
            <div class="inline-block ${bgColor} ${textColor} px-4 py-2 rounded-lg text-sm">
                ${this.escapeHtml(content)}
            </div>
        `;

        this.elements.chatMessages.appendChild(messageDiv);
        messageDiv.scrollIntoView({ behavior: 'smooth' });
    }

    addToolCall(data) {
        if (!this.elements.toolLogs) return;

        // Clear initial message
        const initialMsg = this.elements.toolLogs.querySelector('#no-tools-message');
        if (initialMsg) initialMsg.remove();

        const toolDiv = document.createElement('div');
        toolDiv.className = 'mb-4 p-3 bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm animate-in fade-in slide-in-from-right-4 duration-300';
        toolDiv.dataset.toolName = data.tool;

        toolDiv.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                    <span class="font-bold text-[10px] text-gray-500 uppercase tracking-widest">${this.escapeHtml(data.tool)}</span>
                </div>
                <span class="status-badge text-[9px] px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-bold uppercase">Executing</span>
            </div>
            <div class="text-[11px] font-mono bg-white dark:bg-gray-950 p-2 rounded border border-gray-100 dark:border-gray-800/50 overflow-x-auto text-gray-600 dark:text-gray-400">
                ${this.escapeHtml(JSON.stringify(data.args, null, 1))}
            </div>
            <div class="tool-result-container mt-2"></div>
        `;

        this.elements.toolLogs.appendChild(toolDiv);
        this.elements.toolLogs.scrollTop = this.elements.toolLogs.scrollHeight;

        // Update Stats
        if (this.elements.toolCount) {
            this.elements.toolCount.textContent = parseInt(this.elements.toolCount.textContent) + 1;
        }
    }

    updateToolResult(data) {
        const entries = Array.from(document.querySelectorAll(`[data-tool-name="${data.tool}"]`));
        const toolDiv = entries[entries.length - 1];
        if (!toolDiv) return;

        const resultContainer = toolDiv.querySelector('.tool-result-container');
        const statusBadge = toolDiv.querySelector('.status-badge');
        const pulseDot = toolDiv.querySelector('.animate-pulse');

        if (pulseDot) {
            pulseDot.classList.remove('animate-pulse', 'bg-blue-500');
            pulseDot.classList.add(data.success ? 'bg-green-500' : 'bg-red-500');
        }

        if (statusBadge) {
            statusBadge.textContent = data.success ? 'Success' : 'Failed';
            statusBadge.className = `status-badge text-[9px] px-2 py-0.5 rounded-full font-bold uppercase ${data.success ? 'bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400'}`;
        }

        const resultDiv = document.createElement('div');
        resultDiv.className = 'mt-2 pt-2 border-t border-gray-100 dark:border-gray-800';

        // Truncate display slightly for the UI logs
        const displayResult = data.result.length > 500 ? data.result.substring(0, 500) + '...' : data.result;

        resultDiv.innerHTML = `
            <div class="text-[11px] font-mono p-2 rounded-lg bg-gray-100 dark:bg-gray-950/50 text-gray-700 dark:text-gray-300 overflow-x-auto max-h-[150px]">
                <span class="opacity-50 font-bold uppercase text-[9px]">Output:</span><br>
                ${this.escapeHtml(displayResult)}
            </div>
        `;

        if (resultContainer) resultContainer.appendChild(resultDiv);
        if (this.elements.toolLogs) this.elements.toolLogs.scrollTop = this.elements.toolLogs.scrollHeight;

        // Update Stats Success
        if (data.success && this.elements.toolSuccess) {
            this.elements.toolSuccess.textContent = parseInt(this.elements.toolSuccess.textContent) + 1;
        }
    }

    async loadTools() {
        console.log('Fetching tools...');
        try {
            const response = await fetch('/api/tools');
            const data = await response.json();

            // Clear loading states
            if (this.elements.toolShortcuts) this.elements.toolShortcuts.innerHTML = '';
            const contextToolsList = document.getElementById('context-tools-list');
            if (contextToolsList) contextToolsList.innerHTML = '';

            if (data.tools && data.tools.length > 0) {
                data.tools.forEach(tool => {
                    // Shortcut chips
                    if (this.elements.toolShortcuts) {
                        const button = document.createElement('button');
                        button.className = 'px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-all shadow-sm';
                        button.textContent = tool.name;
                        button.addEventListener('click', () => {
                            this.elements.messageInput.value = `Use ${tool.name} to `;
                            this.elements.messageInput.focus();
                        });
                        this.elements.toolShortcuts.appendChild(button);
                    }

                    // Sidebar Item
                    if (contextToolsList) {
                        const item = document.createElement('div');
                        item.className = 'flex items-center gap-3 text-[11px] p-2 hover:bg-white dark:hover:bg-gray-800 rounded-lg group relative cursor-help border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all';
                        item.innerHTML = `
                            <div class="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]"></div>
                            <span class="truncate text-gray-700 dark:text-gray-300 font-medium">${tool.name}</span>
                            <div class="absolute left-full ml-2 px-3 py-2 bg-gray-900/95 text-white text-[10px] rounded-lg shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none z-[100] whitespace-normal min-w-[200px] border border-gray-700 backdrop-blur-md transition-all duration-300">
                                <div class="font-bold border-b border-gray-700 pb-1 mb-1">${tool.server}</div>
                                ${tool.description}
                            </div>
                        `;
                        contextToolsList.appendChild(item);
                    }
                });

                const toolsCount = document.querySelector('#context-panel-bottom .bg-green-100, #context-panel-bottom .bg-green-900\\/30');
                if (toolsCount) toolsCount.textContent = `${data.tools.length} active`;
            } else {
                if (contextToolsList) contextToolsList.innerHTML = '<div class="text-center py-4 text-xs text-gray-400 italic">No tools found</div>';
            }
        } catch (error) {
            console.error('Failed to load tools:', error);
        }
    }

    async loadStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            // Update system prompt (targeting the new structure)
            const systemPromptEl = document.querySelector('#context-panel-top .bg-white.dark\\:bg-gray-800.rounded-xl.p-3');
            if (systemPromptEl && data.agent.system_prompt) {
                systemPromptEl.textContent = data.agent.system_prompt;
            }

            // Update model list and selection
            if (this.elements.modelSelect && data.agent.available_models) {
                const currentOptions = Array.from(this.elements.modelSelect.options).map(o => o.value);
                const newOptions = data.agent.available_models;

                // Only reconstruct if list is different or empty
                if (JSON.stringify(currentOptions) !== JSON.stringify(newOptions)) {
                    this.elements.modelSelect.innerHTML = newOptions.map(m =>
                        `<option value="${m}" ${m === data.agent.current_model ? 'selected' : ''}>${m}</option>`
                    ).join('');
                } else {
                    if (this.elements.modelSelect.value !== data.agent.current_model) {
                        this.elements.modelSelect.value = data.agent.current_model;
                    }
                }
            }

            // Update temperature
            if (this.elements.temperatureSlider && data.agent.temperature !== undefined) {
                this.elements.temperatureSlider.value = data.agent.temperature;
                this.elements.temperatureValue.textContent = data.agent.temperature;
            }

            this.updateStatus(data.agent.initialized ? data.agent.status : 'initializing');

            // If not initialized, poll until it is
            if (!data.agent.initialized) {
                setTimeout(() => this.loadStatus(), 2000);
            }
        } catch (error) {
            console.error('Failed to load status:', error);
            setTimeout(() => this.loadStatus(), 5000);
        }
    }

    updateStatus(status) {
        const statusColors = {
            idle: 'text-green-500',
            thinking: 'text-yellow-500',
            executing: 'text-blue-500',
            streaming: 'text-purple-500',
            error: 'text-red-500',
            initializing: 'text-yellow-500'
        };

        const statusText = {
            idle: 'Idle',
            thinking: 'Thinking...',
            executing: 'Executing tool...',
            streaming: 'Streaming...',
            error: 'Error',
            initializing: 'Initializing Agent...'
        };

        const statusIndicator = this.elements.statusIndicator;
        if (!statusIndicator) return;

        statusIndicator.className = `text-sm ${statusColors[status] || 'text-gray-500'}`;
        statusIndicator.innerHTML = `● ${statusText[status] || status}`;

        // Disable/enable send button based on status
        if (status === 'initializing') {
            this.elements.sendButton.disabled = true;
            this.elements.messageInput.placeholder = "Please wait, agent is initializing...";
        } else {
            this.elements.sendButton.disabled = !this.elements.messageInput.value.trim();
            this.elements.messageInput.placeholder = "Ask the agent to research, analyze, or execute tools...";
        }
    }

    highlightCodeBlocks(container) {
        container.querySelectorAll('pre code').forEach((block) => {
            const code = block.textContent;
            const language = block.className.replace('language-', '') || 'plaintext';
            block.className = `language-${language}`;
            block.style.fontFamily = "'JetBrains Mono', monospace";
        });
    }

    addCopyButton(messageElement, content) {
        const copyButton = messageElement.querySelector('.copy-btn');
        if (!copyButton) return;

        copyButton.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(content);
                const originalText = copyButton.textContent;
                copyButton.textContent = 'Copied!';
                copyButton.classList.add('text-green-600');

                setTimeout(() => {
                    copyButton.textContent = originalText;
                    copyButton.classList.remove('text-green-600');
                }, 2000);
            } catch (error) {
                console.error('Copy failed:', error);
            }
        });
    }

    async loadSession(sessionId) {
        try {
            const response = await fetch(`/api/sessions/${sessionId}`);
            if (!response.ok) throw new Error('Session not found');

            const session = await response.json();
            this.elements.chatMessages.innerHTML = '';

            session.messages.forEach(msg => {
                this.addMessage(msg.role, msg.content);
            });

            this.addSystemMessage('Session loaded successfully', 'success');
        } catch (error) {
            console.error('Failed to load session:', error);
            localStorage.removeItem('current_session_id');
            this.currentSessionId = null;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.App = new MCPAgentUI();
});
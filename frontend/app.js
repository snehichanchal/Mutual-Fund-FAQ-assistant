const chatArea = document.getElementById('chat-area');
const chatForm = document.getElementById('chat-form');
const queryInput = document.getElementById('query-input');
const sendButton = document.getElementById('send-button');

// Disable/Enable input
function setInputState(disabled) {
    queryInput.disabled = disabled;
    sendButton.disabled = disabled || queryInput.value.trim() === '';
}

// Auto-enable button when text is typed
queryInput.addEventListener('input', () => {
    sendButton.disabled = queryInput.value.trim() === '';
});

function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

function formatAnswerText(text) {
    let html = escapeHTML(text);
    // Convert markdown links [text](url) to html links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    // Convert newlines to <br>
    html = html.replace(/\n/g, '<br>');
    return html;
}

function displayUserMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user-message';
    msgDiv.innerHTML = `<div class="message-bubble">${escapeHTML(text)}</div>`;
    chatArea.appendChild(msgDiv);
    scrollToBottom();
}

function showTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message';
    msgDiv.id = 'typing-indicator';
    msgDiv.innerHTML = `
        <div class="message-bubble">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatArea.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function displayBotMessage(data) {
    removeTypingIndicator();
    const msgDiv = document.createElement('div');
    
    let bubbleClass = 'bot-message';
    if (data.refused) {
        bubbleClass += data.query_type === 'PII' ? ' error' : ' refusal';
    }
    msgDiv.className = `message ${bubbleClass}`;
    
    let html = `<div class="message-bubble"><p>${formatAnswerText(data.answer)}</p>`;
    
    if (data.source_url && !data.refused) {
        html += `
        <div class="citation-footer">
            Source: <a href="${data.source_url}" target="_blank" rel="noopener noreferrer">${data.source_title || 'Link'}</a>
            <br>Last updated: ${data.last_updated || 'Unknown'}
        </div>`;
    }
    
    html += `</div>`;
    msgDiv.innerHTML = html;
    
    chatArea.appendChild(msgDiv);
    scrollToBottom();
}

function displayError(text) {
    removeTypingIndicator();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message error';
    msgDiv.innerHTML = `<div class="message-bubble"><p>${escapeHTML(text)}</p></div>`;
    chatArea.appendChild(msgDiv);
    scrollToBottom();
}

async function sendChatQuery(query) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        });
        
        if (!response.ok) {
            if (response.status === 429) {
                throw new Error("Too many requests. Please slow down.");
            }
            throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("API Error:", error);
        throw error;
    }
}

async function sendMessage(query) {
    if (!query.trim()) return;
    
    // Hide welcome card if visible
    const welcome = document.getElementById('welcome-card');
    if (welcome) welcome.style.display = 'none';

    // 1. Display User message
    displayUserMessage(query);
    queryInput.value = '';
    setInputState(true);

    // 2. Show Typing Indicator
    showTypingIndicator();

    // 3. API Call
    try {
        const responseData = await sendChatQuery(query);
        // 4. Display Bot message
        displayBotMessage(responseData);
    } catch (error) {
        // Display Error message
        displayError(error.message || "Failed to reach the server. Please try again.");
    } finally {
        setInputState(false);
        queryInput.focus();
    }
}

// Event Listeners
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    sendMessage(queryInput.value);
});

// Global function for example chips
window.sendExample = function(query) {
    sendMessage(query);
};

// Initial focus
queryInput.focus();

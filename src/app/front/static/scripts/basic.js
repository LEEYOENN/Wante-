// chat의 session_id로 사용
// 로컬 스토리지에 해당 정보 저장 후 사용
// 저장된 값이 있으면 해당 정보 사용
const _local_user_id = localStorage.getItem('wantedash-userid')
const userSession = _local_user_id ? _local_user_id : 'user::'+crypto.randomUUID();
if(_local_user_id == null){
    localStorage.setItem('wantedash-userid', userSession)
}
console.log("USER SESSION ID : " + userSession)

let messages = [];
let isLoading = false;
let chatSessions = [];
let currentSessionId = crypto.randomUUID();
// ===== 현재 선택된 API 엔드포인트 (기본값은 제출관련 업무 agent)=====
let currentApiEndpoint = 'http://localhost:8000/api/chatbot/submit'

const AGENT_JOB_LISTS = {
    'alarm': [
        'DM으로 자유 형식 공지 전송',
        '특정 채널로 자유 형식 공지 전송',
        '보고서 미제출자 DM 알림',
        'Today 공지 사항 전송'
    ],
    'rag': [
        '운영 문의 답변',
        '학생 상담',
        '잡담'
    ]
}
// api 에서 가져올 submit job list
let submit_job_list = [];
// 현재 welcome screen에 표시될 job 목록
let agent_job_list = [];

const chatArea = document.getElementById('chatArea');
const chatContent = document.getElementById('chatContent');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const welcomeScreen = document.getElementById('welcomeScreen');

// Auto-resize textarea
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// Handle Enter key
messageInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Toggle Sidebar (Mobile)
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('active');
}

// Toggle Settings
function toggleSettings() {
    const panel = document.getElementById('settingsPanel');
    panel.classList.toggle('active');
}
// == 에이전트 선택 함수 ==
function selectAgent(agentKey, apiEndpoint) {
    // apiEndpoint 업데이트
    currentApiEndpoint = `http://localhost:8000${apiEndpoint}`;

    // 버튼 활성화 / 비활성화 처리
    document.querySelectorAll('.agent-btn').forEach(btn => {
        btn.classList.remove('active');
    })
    document.getElementById(`agent-btn-${agentKey}`).classList.add('active');

    if (agentKey === 'submit') {
        agent_job_list = submit_job_list;
    } else {
        agent_job_list = AGENT_JOB_LISTS[agentKey] || [];
    }
    // document.getElementById('agent-btn-submit').classList.remove('active');
    // document.getElementById('agent-btn-alarm').classList.remove('active');
    // document.getElementById('agent-btn-rag').classList.remove('active');

    // if (agentKey === 'submit') {
    //     document.getElementById('agent-btn-submit').classList.add('active');
    // }
    // else if (agentKey === 'alarm') {
    //     document.getElementById('agent-btn-alarm').classList.add('active');
    // }
    // else if (agentKey === 'rag') {
    //     document.getElementById('agent-btn-rag').classList.add('active');
    // }
    // (선택 사항) 에이전트를 바꾸면 새 대화로 시작
    // 이 부분을 주석 처리하면 에이전트를 바꿔도 기존 대화가 유지됩니다.
    newChat();

    console.log(`Agent switched to: ${agentKey}, Endpoint: ${currentApiEndpoint}`);

    
}   
// New Chat
function newChat() {
    currentSessionId = crypto.randomUUID();
    chatSessions.push({
        id: currentSessionId,
        title: newChatTitle(),
        messages: []
    });
    chatContent.innerHTML = '';
    welcomeScreen.style.display = 'block';

    // 'Current'의 messages = [] 로직을 'Incoming'의 is_first 조건문과 결합
    // (단, 'Incoming' 코드에서 이 부분이 주석처리 되어있었으므로 필요시 주석 해제
    // if(!is_first)
    // {
    //     messages = [];
    // }

    updateChatHistory();
    showWelcomeScreen();
}

// Update Chat History
function updateChatHistory() {
    const historyEl = document.getElementById('chatHistory');
    const reversedSessions = chatSessions.slice().reverse();
    let html = '';
    for (let i = 0; i < reversedSessions.length; i++) {
        const session = reversedSessions[i];
        const isActive = session.id === currentSessionId ? 'active' : '';
        // 'session.id'를 따옴표로 감싸는 'Incoming' 방식 사용
        html += '<div class="chat-item ' + isActive + '" onclick="loadSession(\'' + session.id + '\')">';
        html += '<span class="chat-item-icon">💬</span>';
        html += '<span class="chat-item-text">' + session.title + '</span>';
        html += '</div>';
    }
    historyEl.innerHTML = html;
}

// Load Session
function loadSession(sessionId) {
    const session = chatSessions.find(s => s.id === sessionId);
    if (session) {
        currentSessionId = sessionId;
        messages = session.messages;
        chatContent.innerHTML = '';
        
        if (messages.length === 0) {
            // welcomeScreen.style.display = 'block';
            showWelcomeScreen();
        } else {
            welcomeScreen.style.display = 'none';
            messages.forEach(msg => {
                addMessageToUI(msg.role, msg.content, msg.timestamp);
            });
        }
        updateChatHistory();
    }
}

// Set Input
function setInput(text) {
    messageInput.value = text;
    messageInput.focus();
}

// Clear Chat
function clearChat() {
    if (confirm('현재 대화 내용을 삭제하시겠습니까?')) {
        const session = chatSessions.find(s => s.id === currentSessionId);
        if (session) {
            session.messages = [];
        }
        messages = [];
        chatContent.innerHTML = '';
        // welcomeScreen.style.display = 'none';
        showWelcomeScreen();
    }
}

// Scroll to Bottom
function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}

// Add Message to UI ) Incoming'의 addMessageToUI (welcomeScreen 처리 방식 채택))
function addMessageToUI(role, content, timestamp) {
    welcomeScreen.style.display = 'none'
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🧞';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content-wrapper">
            <div class="message-content">${content}</div>
            <div class="message-time">${timestamp}</div>
        </div>
    `;
    
    chatContent.appendChild(messageDiv);
    scrollToBottom();
}

// Show Loading
function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.id = 'loadingIndicator';
    
    loadingDiv.innerHTML = `
        <div class="message-avatar">🧞</div>
        <div class="loading-content">
            <div class="spinner"></div>
            <span>생각하는 중...</span>
        </div>
    `;
    
    chatContent.appendChild(loadingDiv);
    scrollToBottom();
}

// Hide Loading
function hideLoading() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

// 초기 초대 항목 등록 하기 ('Incoming'의 초기화 및 History 로직 전체)
console.log('초기 항목 등록하기');

function makeChatJob(last_content){
    for(job of agent_job_list.slice(1)){
        if(last_content.includes(job)) return job;
    }
    return agent_job_list[0];
}

//Show Welcome Screen
function showWelcomeScreen(){
    console.log(agent_job_list);
    welcomeScreen.style.display = 'block';
    const grid = document.getElementById('welcomeGrid');
    // 중복 생성을 막기 위해 기존 내용 삭제
    grid.innerHTML = ''; 
    agent_job_list.forEach(job => {
        const card = document.createElement('div');
        card.classList.add('example-card');
        card.innerHTML = `<p>${job}</p>`;
        card.addEventListener('click', function() {
            setInput(job)
        });
        grid.appendChild(card);
    })
}

(async () => {
    // 'Incoming' 코드는 fetch_get을 사용합니다.
    const job_list = await fetch_get('JOBS'); 
    const welcome_data = ['업무 문의']
    const history = await fetch_get('HISTORY',id=userSession);

    // 불러온 데이터 처리(welcome card, history list)
    // welcome_data.concat(job_list['jobs']).forEach(data => {
    //     agent_job_list.push(data);
    // });

    // submit' 에이전트 목록을 전역 변수에 저장
    submit_job_list = welcome_data.concat(job_list['jobs'] || []);

    // 현재 agent_job_list를 기본값('submit')으로 설정
    agent_job_list = submit_job_list

    if(history && history.result){ // history.result가 있는지 확인
        //1 session 리스트 가져오기
        const session_list = [...new Set(history.result.map(message => message.conversation_id))]
        let count = 1;
        let _chat_title = ''
        for(const _id of session_list){
            const _messages = []
            //2. 각 session의 메시지 리스트 가져오기
            const _id_messages = history.result.filter(message => message.conversation_id === _id)
            _id_messages.forEach((message,idx) => {
                if(idx === 0){
                    _chat_title = makeChatTitle(new Date(message.created_at));
                }
                if(message.type === 'HUMAN'){
                    _messages.push({
                        role: 'user',
                        content: message.content,
                        timestamp: getChatTime(new Date(message.created_at))
                    });
                }else if(message.type === 'AI'){
                    _messages.push({
                        role: 'assistant',
                        content: message.content,
                        timestamp: getChatTime(new Date(message.created_at))
                    });
                }
            })
            chatSessions.push({
                id: _id,
                title: makeChatJob(_messages.at(-1).content)+`( ${_chat_title} )`, //_chat_title,  //`히스토리 ${count}`,
                messages: _messages
            });
            count ++;
        }
    }
    
    // 'Current' 코드의 첫 세션 생성 로직 대신 'Incoming'의 로직 사용
    // chatSessions.push({
    //  id: currentSessionId,
    //  title: '새로운 대화',
    //  messages: []
    // });
    
    newChat(true); // 'Incoming'의 히스토리 로딩 후 새 대화 시작
    // showWelcomeScreen();
})();


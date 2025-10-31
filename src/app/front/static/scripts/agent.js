// 파일 업로드가 필수 인지 체크용
let is_fileupload = false;
// 파일 처리 스크립트
const messageFile = document.getElementById('messageFile');
const messageLabel = document.getElementById('messageLabel');
const fileNameSpan = document.querySelector('.file-name');

messageFile.addEventListener('click', function(event){
    if(!is_fileupload){
        console.log('파일 업로드가 필수가 아닙니다.');
        return;
    }
    console.log('click');
})

// fileInput의 값이 바뀔 때(파일이 선택될 때)마다 실행됩니다.
messageFile.addEventListener('change', function(event) {
    // 파일이 선택되었는지 확인
    console.log('change');
    console.log(event);
    if (this.files && this.files.length > 0) {
        // 선택된 파일이 1개 이상이면, 첫 번째 파일의 이름을 span에 표시
        fileNameSpan.textContent = this.files[0].name;
    } else {
        // 파일 선택이 취소된 경우 (혹은 파일이 없는 경우)
        fileNameSpan.textContent = '선택된 파일 없음';
    }
});

function toggleFileUpload(data){
    // 파일 업로드 기능을 필수 인지 체크
    // AI agent 결과 메시지에서 필수 항목에 로컬 파일이 있는 경우만 필수 처리
    console.log('**** toggle file button ****')
    console.log(data)
    if (data.output &&data.output.includes('로컬 파일')){
        is_fileupload = true
        messageFile.disabled = false
        messageLabel.style.backgroundColor = '#007bff'
    } else {
        is_fileupload = false
        messageFile.disabled = true
        messageLabel.style.backgroundColor = 'gray'
    }
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isLoading) return;

    const timestamp = getCurrentTime();
    const userMsg = { role: 'user', content: message, timestamp };
    
    addMessageToUI('user', message, timestamp);
    messages.push(userMsg);

    // 세션 업데이트
    const session = chatSessions.find(s => s.id === currentSessionId);
    if (session) {
        session.messages = messages;
        if (session.title === '새로운 대화') {
            session.title = message.substring(0, 30) + (message.length > 30 ? '...' : '');
            updateChatHistory();
        }
    }
    
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    isLoading = true;
    sendBtn.disabled = true;
    sendBtn.innerHTML = '⏳';
    showLoading();
    
    // api 엔드 포인트에 따라 요청 옵션을 분리
    let fetchOptions;

    if (currentApiEndpoint.includes('api/chatbot/alarm') || currentApiEndpoint.includes('api/chatbot/rag')) {
        // Alarm 에이전트는 json 형식으로 전송
        const jsonData = {
            question: message
        };

        fetchOptions = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(jsonData)
        };
    } else {
        // 제출관련 에이전트라면 폼 데이터 생성
        const formData = new FormData();

        formData.append("id", userSession)
        formData.append("session_id",currentSessionId);
        formData.append("message", message);

        // 선택한 파일중 마지막 파일 등록, 파일 등록이 필수 일 경우만 전송
        if(is_fileupload & messageFile.files.length > 0)
            formData.append("file", messageFile.files[0]);
            messageFile.value = null;
            fileNameSpan.textContent = '선택된 파일 없음';
        // console.log('***** form data *****')
        // console.log(formData)

        fetchOptions = {
            method: 'POST',
            body: formData
            // FormData는 headers를 자동으로 설정합니다.
        };
    }


    //함수호출
    try {
        // 'currentApiEndpoint'와 'fetchOptions'를 사용해 요청
        const response = await fetch(currentApiEndpoint, fetchOptions);

        const data = await response.json();
        console.log("***** result *****")
        console.log(data);
        hideLoading();
        
        // 서버 응답에 맞춰서 AI 응답 처리
        let aiResponse = '';

        if (data.data && data.data.answer) {
            aiResponse = data.data.answer;
        } 
        else if (data.output) {
            aiResponse = data.output;
        } 
        else {
            aiResponse = '응답 형식을 처리할 수 없습니다.';
        }

        const aiTimestamp = getCurrentTime();
        addMessageToUI('assistant',  aiResponse, aiTimestamp);
        messages.push({ role: 'assistant', content: aiResponse, timestamp: aiTimestamp });
        
        if (data.output) {
            toggleFileUpload(data);
        } else {
            toggleFileUpload({output: ''});// '로컬 파일'이 없는 응답으로 처리
        }
        

    } catch (error) {
        console.error('Error:', error);
        hideLoading();
        addMessageToUI('assistant', '오류가 발생했습니다. 다시 시도해주세요.', getCurrentTime());
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        sendBtn.innerHTML = '➤';
    }       
}
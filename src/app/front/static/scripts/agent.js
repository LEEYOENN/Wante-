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
    if(data.output.includes('로컬 파일')){
        is_fileupload = true
        messageFile.disabled = false
        messageLabel.style.backgroundColor = '#007bff'
    }else{
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
    // Update session
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
    
    // 폼 데이터 생성
    const formData = new FormData();
    formData.append("id",currentSessionId);
    formData.append("message", message);
    // 선택한 파일중 마지막 파일 등록, 파일 등록이 필수 일 경우만 전송
    if(is_fileupload & messageFile.files.length > 0)
        formData.append("file", messageFile.files[0]);
        messageFile.value = null;
        fileNameSpan.textContent = '선택된 파일 없음';
    // console.log('***** form data *****')
    // console.log(formData)

    //함수호출
    try {
        const response = await fetch('http://localhost:8000/api/chat', {
            method: 'POST',
            body: formData,
            // headers: {
            //     'Content-Type': 'application/json',
            // },
            // body: JSON.stringify({
            //     message: message
            // })
        });
        const data = await response.json();
        console.log("***** result *****")
        console.log(data);
        hideLoading();        
        const aiTimestamp = getCurrentTime();
        addMessageToUI('assistant', data.output, aiTimestamp);
        messages.push({ role: 'assistant', content: data.output, timestamp: aiTimestamp });
        toggleFileUpload(data);
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
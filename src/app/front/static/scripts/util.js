function makeChatTitle(_date){
    const year = _date.getFullYear();
    const month = _date.getMonth() + 1; // 0부터 시작하므로 +1
    const date = _date.getDate();
    const hours = _date.getHours();
    const minutes = _date.getMinutes();
    const seconds = _date.getSeconds();
    return `${year}/${month}/${date} ${hours}:${minutes}:${seconds}`
}

function newChatTitle(){
    const now = new Date();
    return makeChatTitle(now);
}

function getChatTime(date){
    return date.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

function getCurrentTime() {
    return getChatTime(new Date());
}

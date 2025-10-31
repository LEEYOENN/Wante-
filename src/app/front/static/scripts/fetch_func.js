BASE_URL = 'http://localhost:8000';
API_MAP = {
    'JOBS':'/jobs',
    'HISTORY':'/api/messages',
    'SUBMIT':'/api/chatbot/submit',
    'ALARM':'/api/chatbot/alarm',
    'RAG':'/api/chatbot/rag',
}
async function fetch_get(key, id){
    console.log('********** fetch(get) **********')
    const url = `${BASE_URL}${API_MAP[key]}${id === undefined? '' : '/'+id}`
    console.log(url);
    const results = await fetch(url).then(res => res.json());
    console.log(results)
    console.log('********** fetch **********')
    return results;
}

// async function fetch_post(key, form){
//     console.log('********** fetch(post) **********')
//     url = `${BASE_URL}${API_MAP[key]}${id ? id : ''}`
//     console.log(url);
//     const results = await fetch('http://localhost:8000/api/chatbot/submit', {
//             method: 'POST',
//             body: form,
//         }).then(res => res.json());
//     console.log(results)
//     console.log('********** fetch **********')
//     return results;
// }

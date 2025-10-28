document.addEventListener('DOMContentLoaded', () => {

    // --- 데이터 (실제로는 서버 API를 통해 관리) ---
    let courses = [
        { id: 1, name: 'AI 에이전트 개발 과정', instructor: '김지민', students: ['박서준', '이수아'] },
        { id: 2, name: 'React 프론트엔드 실전', instructor: '최유리', students: ['정다은'] },
        { id: 3, name: 'Docker 컨테이너 입문', instructor: '박진우', students: [] }
    ];

    // --- DOM 요소 가져오기 ---
    const studentView = document.getElementById('studentView');
    const adminView = document.getElementById('adminView');
    const showStudentViewBtn = document.getElementById('showStudentView');
    const showAdminViewBtn = document.getElementById('showAdminView');

    const studentCourseList = document.getElementById('studentCourseList');
    const adminCourseList = document.getElementById('adminCourseList');

    const addCourseForm = document.getElementById('addCourseForm');
    const chatForm = document.getElementById('chatForm');
    const chatHistory = document.getElementById('chatHistory');
    const userInput = document.getElementById('userInput');
    
    const modal = document.getElementById('studentListModal');
    const modalCourseName = document.getElementById('modalCourseName');
    const modalStudentList = document.getElementById('modalStudentList');
    const closeButton = document.querySelector('.close-button');


    // --- 함수 정의 ---

    // 화면 렌더링 함수
    function renderCourses() {
        studentCourseList.innerHTML = '';
        adminCourseList.innerHTML = '';

        courses.forEach(course => {
            // 학생 페이지 목록 렌더링
            const studentLi = document.createElement('li');
            studentLi.innerHTML = `
                <div class="course-info">
                    <h3>${course.name}</h3>
                    <p>강사: ${course.instructor}</p>
                </div>
                <button class="btn register-btn" data-id="${course.id}">수강 신청</button>
            `;
            studentCourseList.appendChild(studentLi);

            // 관리자 페이지 목록 렌더링
            const adminLi = document.createElement('li');
            adminLi.innerHTML = `
                <div class="course-info">
                    <h3>${course.name}</h3>
                    <p>강사: ${course.instructor} | 수강생: ${course.students.length}명</p>
                </div>
                <button class="btn btn-secondary view-students-btn" data-id="${course.id}">수강생 보기</button>
            `;
            adminCourseList.appendChild(adminLi);
        });
    }

    // 화면 전환 함수
    function switchView(viewToShow) {
        if (viewToShow === 'student') {
            studentView.style.display = 'block';
            adminView.style.display = 'none';
            showStudentViewBtn.classList.add('active');
            showAdminViewBtn.classList.remove('active');
        } else {
            studentView.style.display = 'none';
            adminView.style.display = 'block';
            showStudentViewBtn.classList.remove('active');
            showAdminViewBtn.classList.add('active');
        }
    }
    
    // 채팅 메시지 추가 함수
    function addChatMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', sender === 'user' ? 'user-message' : 'agent-message');
        messageDiv.textContent = text;
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight; // 항상 마지막 메시지가 보이도록 스크롤
    }


    // --- 이벤트 리스너 ---

    // 뷰 전환 버튼
    showStudentViewBtn.addEventListener('click', () => switchView('student'));
    showAdminViewBtn.addEventListener('click', () => switchView('admin'));

    // 관리자: 과정 추가
    addCourseForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const courseName = document.getElementById('courseName').value;
        const instructorName = document.getElementById('instructorName').value;

        const newCourse = {
            id: courses.length > 0 ? Math.max(...courses.map(c => c.id)) + 1 : 1,
            name: courseName,
            instructor: instructorName,
            students: []
        };
        courses.push(newCourse);
        renderCourses();
        addCourseForm.reset();
    });

    // 학생: 수강 신청 (이벤트 위임)
    studentCourseList.addEventListener('click', (e) => {
        if (e.target.classList.contains('register-btn')) {
            const courseId = parseInt(e.target.dataset.id, 10);
            const course = courses.find(c => c.id === courseId);
            // 실제 애플리케이션에서는 로그인된 학생의 정보를 사용합니다.
            const studentName = prompt(`'${course.name}' 과정에 등록할 학생의 이름을 입력하세요:`, "홍길동");
            if (studentName) {
                course.students.push(studentName);
                alert(`'${studentName}'님, '${course.name}' 과정 등록이 완료되었습니다.`);
                renderCourses(); // 수강생 수 업데이트를 위해 다시 렌더링
            }
        }
    });

    // 관리자: 수강생 보기 (이벤트 위임)
    adminCourseList.addEventListener('click', (e) => {
        if (e.target.classList.contains('view-students-btn')) {
            const courseId = parseInt(e.target.dataset.id, 10);
            const course = courses.find(c => c.id === courseId);
            
            modalCourseName.textContent = `"${course.name}" 과정 수강생 (${course.students.length}명)`;
            modalStudentList.innerHTML = '';
            
            if (course.students.length > 0) {
                course.students.forEach(student => {
                    const li = document.createElement('li');
                    li.textContent = student;
                    modalStudentList.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.textContent = '아직 등록한 학생이 없습니다.';
                modalStudentList.appendChild(li);
            }
            modal.style.display = 'block';
        }
    });

    // 학생: AI 에이전트 문의
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        addChatMessage('user', message);
        userInput.value = '';

        // AI 응답 시뮬레이션
        setTimeout(() => {
            addChatMessage('agent', `"${message}"에 대한 답변을 생성 중입니다...`);
        }, 1000);
    });

    // 모달 닫기
    closeButton.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });


    // --- 초기화 ---
    renderCourses();
});
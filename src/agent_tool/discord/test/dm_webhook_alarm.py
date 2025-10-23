import requests
import json

WEBHOOK_URL = "디스코드에서 복사한 웹훅 URL"
MESSAGE_CONTENT = "🚨 외부 시스템에서 웹훅을 통해 보낸 알림입니다!"

data = {
    "content": MESSAGE_CONTENT,
    # "username": "사용자 정의 이름" (봇 이름 대신 표시)
}

# HTTP POST 요청을 보냄
response = requests.post(
    WEBHOOK_URL,
    data=json.dumps(data),
    headers={"Content-Type": "application/json"}
)

if response.status_code == 204:
    print("웹훅 메시지 전송 성공!")
else:
    print(f"웹훅 메시지 전송 실패: {response.status_code}")
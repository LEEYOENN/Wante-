import discord
import sqlite3
import os
from dotenv import load_dotenv
import discord.ui

# RAG 핵심 로직 임포트
from rag_core import create_langgraph_chain, setup_database, log_chat, LOG_DB_PATH

# 환경 설정 및 RAG 체인 로드
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# API 키 확인
if not os.getenv("OPENAI_API_KEY"):
    print("[시작 오류] .env 파일에 'OPENAI_API_KEY'가 설정되지 않았습니다.")
    exit()
if not DISCORD_TOKEN:
    print("[시작 오류] .env 파일에 'DISCORD_TOKEN'이 설정되지 않았습니다.")
    exit()

# LangGraph 체인 준비
try:
    langgraph_chain = create_langgraph_chain()
    setup_database()
except FileNotFoundError as e:
    print(f"[시작 오류] {e}")
    exit()
except Exception as e:
    print(f"[시작 오류] Fatal error loading RAG chain: {e}")
    exit()


# MediaRequestView
class MediaRequestView(discord.ui.View):
    def __init__(self, file_paths: list[str]):
        super().__init__(timeout=180)
        self.file_paths = file_paths

    @discord.ui.button(label="관련 표/이미지 보기", style=discord.ButtonStyle.primary)
    async def send_media_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # ephemeral= True: 버튼을 클릭한 사용자에게만 이 메세지가 보임
        await interaction.response.defer(ephemeral=True, thinking=True)

        file_list = []
        for file_path in self.file_paths:
            if os.path.exists(file_path):
                file_list.append(discord.File(file_path))
            else:
                print(f"[View 오류] 파일을 찾을 수 없음: {file_path}")

        if file_list:
            await interaction.followup.send(
                "요청하신 관련 자료입니다.:", files=file_list, ephemeral=True
            )
        else:
            await interaction.followup.send(
                "죄송합니다. 요청하신 파일을 처리하는 중 오류가 발생합니다.",
                ephemeral=True,
            )

        # 버튼 비활성화
        button.disabled = True
        button.label = "자료 전송 완료"
        await interaction.message.edit(view=self)  # 원본 메세지의 버튼을 수정


# SatisfactionView
class SatisfactionView(discord.ui.View):
    def __init__(self, log_id: int):  # 어떤 로그에 대한 만족도인지 ID를 받음
        super().__init__(timeout=300)  # 5분 후 비활성화
        self.log_id = log_id

    def update_satisfaction(self, log_id: int, score: int):
        try:
            conn = sqlite3.connect(LOG_DB_PATH, timeout= 10)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_logs SET satisfaction = ? WHERE id = ?", (score, log_id)
            )
            conn.commit()
            conn.close()
            print(f"[만족도] Log ID {log_id} 에 {score} 점 업데이트 완료.")
        except Exception as e:
            print(f"[오류] 만족도 DB 업데이트 실패: {e}")

    @discord.ui.button(label="유용했어요", style=discord.ButtonStyle.success)
    async def useful_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.update_satisfaction(self.log_id, 1)
        # DB의 log_id에 'satisfaction = 1' 업데이터 로직
        print(f"[만족도] Log ID {self.log_id}: 유용함")
        await interaction.response.send_message("피드백 감사합니다! ", ephemeral=True)

        # 모든 버튼 비활성화
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(content="피드백 감사합니다!", view=self)

    @discord.ui.button(label="개선이 필요해요", style=discord.ButtonStyle.danger)
    async def improve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # DB의 log_id에 'satisfaction = -1' 업데이트 로직
        self.update_satisfaction(self.log_id, -1)
        print(f"[만족도] Log ID {self.log_id}: 개선 필요")
        await interaction.response.send_message(
            "소중한 의견 감사합니다. 개선에 참고 하겠습니다.", ephemeral=True
        )

        # 모든 버튼 비활성화
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(content="피드백 감사합니다!", view=self)


# Discord 봇 클라이언트 정의
intents = discord.Intents.default()
intents.message_content = True


class WanteDashBot(discord.Client):
    async def on_ready(self):
        print(f"봇 준비 완료! {self.user} 로 로그인 했습니다.")
        print("--- 봇이 DM 또는 채널 멘션을 기다립니다 ---")

    async def on_message(self, message):
        # 봇 자신의 메세지는 무시
        if message.author == self.user:
            return

        # DM으로 왔는 지 확인 (서버 정보가 없음)
        is_dm = message.guild is None

        # 서버 채널에 봇을 멘션했는 지 확인
        mentioned_in_channel = False if is_dm else self.user.mentioned_in(message)

        # DM 이거나 또는 채널에서 멘션 되었을 때만 응답
        if not (is_dm or mentioned_in_channel):
            return  # DM도 멘션도 아니면 무시

        # 질문 내용 추출
        question = ""
        if is_dm:
            question = message.content.strip()
            print(f"[DM 수신] {message.author}: {question}")
        else:
            question = message.content.replace(f"<@{self.user.id}>", "").strip()
            print(f"\n[{message.guild.name} 채널] {message.author}: {question}")

        if not question:
            await message.channel.send("안녕하세요! 질문을 입력해주세요.")
            return

        # LangGraph 체인 호출
        print(f"-> LangGraph 호출...")
        await message.channel.typing()

        try:
            # LangGraph 호출 방식 (대화 기록 전달)
            config = {"configurable": {"thread_id": f"discord_{message.author.id}"}}
            inputs = {"messages": [("user", question)]}

            # .invoke()를 사용해 최종 State를 한번에 받음
            final_state = langgraph_chain.invoke(inputs, config=config)

            # State에서 answer와 route 추출
            text_answer = final_state.get(
                "answer", "죄송합니다. 답변을 생성하지 못 했습니다."
            )
            route = final_state.get("route", "error")  # 라우팅 경로
            await message.channel.send(text_answer)

            # Rag 라우트 일 때만 미디어 버튼 전송
            media_view = None
            if route == "rag":
                retrieved_docs = final_state.get("context", [])
                relevant_media_paths = []

                for doc in retrieved_docs:
                    doc_type = doc.metadata.get("type")
                    file_path = doc.metadata.get("path")
                    if (
                        doc_type in ["image", "table"]
                        and file_path
                        and os.path.exists(file_path)
                    ):
                        if file_path not in relevant_media_paths:
                            relevant_media_paths.append(file_path)

                if relevant_media_paths:
                    print(
                        f"-> {len(relevant_media_paths)} 개의 관련 미디어를 찾음. 버튼 전송."
                    )
                    media_view = MediaRequestView(file_paths=relevant_media_paths)
                    await message.channel.send(
                        "답변과 관련된 표 자료를 찾았습니다. 보시겠습니까?",
                        view=media_view,
                    )

            # Save Log (include route)
            log_id = log_chat(
                user_name=str(message.author),
                is_dm=is_dm,
                question=question,
                answer=text_answer,
                retrieved_docs=final_state.get("context", []),
                route=route,
            )
            # og_chat이 방금 INSERT된 ID를 반환하도록 수정
            # log_id = get_last_insert_id()

            if route in ["rag", "counseling"] and log_id is not None:
                satisfaction_view = SatisfactionView(log_id=log_id)
                # log_id 없이 임시 ID로 전송
                await message.channel.send(
                    "방금 답변이 유용하셨나요?", view=satisfaction_view
                )

        except Exception as e:
            print(f"[오류] LangGraph 실행 중 오류: {e}")
            await message.channel.send(
                "죄송합니다. 답변을 처리하는 중 오류가 발생했습니다."
            )


# 봇 실행
if __name__ == "__main__":
    client = WanteDashBot(intents=intents)
    client.run(DISCORD_TOKEN)
